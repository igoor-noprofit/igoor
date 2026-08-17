var data = {
  pywebviewready: false,
};
let app;

// Expose the build version so assets whose URL is built client-side (e.g. the
// locale JSON fetched in BasePluginComponent.js) can cache-bust with ?v=<version>,
// matching the ?v={{VERSION}} convention used on app.js / app.vue / component URLs.
window.IGOOR_VERSION = "{{VERSION}}";

function registerReadypy(fn) {
  if (typeof window === "undefined") {
    return;
  }

  const registerFn = window.__app_register_readypy;
  const pending = window.__app_pending_readypy;

  if (typeof registerFn === "function") {
    registerFn(fn);
    return;
  }

  window.app = window.app || {};
  window.app.readypy = fn;

  if (Array.isArray(pending)) {
    while (pending.length) {
      const args = pending.shift();
      try {
        fn(...(Array.isArray(args) ? args : []));
      } catch (error) {
        console.error("Deferred readypy call failed", error);
      }
    }
  }
}

const backendApiReady = import("/js/backend_api.js?v={{VERSION}}").then((module) => {
  if (module?.backendApi && typeof window !== "undefined") {
    window.backendApi = module.backendApi;
    window.dispatchEvent(new Event("backendApiReady"));
  }
  return module?.backendApi;
});

window.addEventListener("pywebviewready", () => {
  console.log("✅ pywebviewready fired");
});

/*
if ('AmbientLightSensor' in window) {
  alert("Ambient Light Sensor detected");
} else {
  console.log("No Ambient Light Sensor available");
}
*/

const options = {
  moduleCache: {
    vue: Vue,
  },

  getFile(url) {
    return fetch(url).then((response) =>
      response.ok ? response.text() : Promise.reject(response)
    );
  },

  addStyle(styleStr) {
    const style = document.createElement("style");
    style.textContent = styleStr;
    const ref = document.head.getElementsByTagName("style")[0] || null;
    document.head.insertBefore(style, ref);
  },

  log(type, ...args) {
    console.log(type, ...args);
  },
};
const backendApiPromise = window.ensureBackendApi();
const { loadModule, version } = window["vue3-sfc-loader"];
async function initializeApp() {
  console.log("initializing app");
  const appTemplate = await options.getFile("/js/app.vue?v={{VERSION}}");
  app = Vue.createApp({
    data() {
      return {
        appview: "loading",
        lastview: "daily",
        websocketUtil: null,
        audioStream: null,
        minimized: false,
        headerExpanded: false,
        pywebviewready: false,
        lang: "{{LANG}}",
        footerShrink: false,
        bootReady: 0,
        bootTotal: 0,
        bootProgressVisible: false,
        bootProgressFaded: false,
        bootProgressHideTimer: null,
        bootNotReady: [],
        bootNotReadyVisible: false,
      };
    },
    components: {
      //** JS_COMPONENTS */
    },
    template: appTemplate,
    computed: {
      bootProgressPercent() {
        if (!this.bootTotal) {
          return 0;
        }
        const percent = Math.round((this.bootReady / this.bootTotal) * 100);
        return Math.min(100, Math.max(0, percent));
      },
      bootNotReadyList() {
        if (!Array.isArray(this.bootNotReady)) {
          return [];
        }
        return this.bootNotReady.slice().sort();
      },
    },
    async mounted() {
      console.warn("APP MOUNTED");
      const backendApi = await backendApiPromise;
      if (!backendApi.isBridgeAvailable && !this.pywebviewready) {
        await this.readypy();
      }
      if (this.appview === "loading") {
        this.appview = this.lastview;
      }
      
      // Listen for footer shrink events from shortcuts component
      window.addEventListener('footer-shrink', (event) => {
        this.footerShrink = event.detail;
      });
    },
    methods: {
      async readypy() {
        this.pywebviewready = true;
        console.warn("Pywebview is ready!");
        const backendApi = await backendApiPromise;
        await backendApi.waitUntilReady();
        this.connectAppWebSocket();
      },
      connectAppWebSocket() {
        const socketUrl = `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.host}/ws/app`;
        this.websocketUtil = new WebSocket(socketUrl);
        // Binary frames carry streamed TTS audio chunks
        this.websocketUtil.binaryType = "arraybuffer";

        this.websocketUtil.onopen = () => {
          console.log("APP WebSocket connection opened");
        };

        this.websocketUtil.onmessage = (event) => {
          if (event.data instanceof ArrayBuffer) {
            this.$_onAudioStreamChunk(event.data);
            return;
          }
          console.log("APP received message on websocket:", event.data);
          try {
            const message = JSON.parse(event.data);
            if (message.type === "boot_progress") {
              this.updateBootProgress(message);
              return;
            }
            if (message.play_stream) {
              this.$_startAudioStream(message.play_stream);
              return;
            }
            if (message.play_stream_end) {
              this.$_endAudioStream(message.play_stream_end);
              return;
            }
            if (message.backend === "addmsg") {
              this.changeView("flow");
            }
            if (message.switchview && message.switchview !== "") {
              this.changeView(message.switchview);
            }
            if (message.minimize) {
              this.minimize();
            }
          } catch (error) {
            console.error("Error parsing WebSocket message:", error);
          }
        };

        this.websocketUtil.onclose = () => {
          console.log("WebSocket connection closed");
          setTimeout(() => this.connectAppWebSocket(), 1000);
        };

        this.websocketUtil.onerror = (error) => {
          console.error("WebSocket error:", error);
        };
      },
      $_stopAudioStream() {
        const stream = this.audioStream;
        if (!stream) return;
        this.audioStream = null;
        try {
          if (stream.audio) {
            stream.audio.onended = null;
            stream.audio.onerror = null;
            stream.audio.pause();
          }
        } catch (e) {
          // audio element already torn down
        }
        try {
          if (stream.sourceBuffer && stream.sourceBuffer.updating) stream.sourceBuffer.abort();
        } catch (e) {
          // source buffer already detached
        }
        try {
          if (stream.mediaSource && stream.mediaSource.readyState === "open") stream.mediaSource.endOfStream();
        } catch (e) {
          // media source already closed
        }
        if (stream.objectUrl) URL.revokeObjectURL(stream.objectUrl);
        if (stream.completionTimer) clearTimeout(stream.completionTimer);
        try {
          if (stream.pcm && stream.pcm.ctx) stream.pcm.ctx.close();
        } catch (e) {
          // audio context already closed
        }
      },
      $_startAudioStream(spec) {
        this.$_stopAudioStream();
        const stream = {
          id: spec.id,
          mime: spec.mime,
          queue: [],
          ended: false,
          started: false,
          confirmedPlaying: false,
          completionTimer: null,
          mediaSource: null,
          sourceBuffer: null,
          audio: null,
          objectUrl: null,
          chunks: null,
          pcm: null,
        };
        this.audioStream = stream;
        const pcmRate = this.$_pcmRate(spec.mime);
        if (pcmRate) {
          // Raw PCM chunks play through WebAudio: MediaSource has no PCM/WAV
          // support, and waiting for the whole clip would forfeit the point
          // of streaming generation.
          stream.pcm = { rate: pcmRate, ctx: null, nextTime: 0 };
        } else if (window.MediaSource && MediaSource.isTypeSupported(spec.mime)) {
          stream.mediaSource = new MediaSource();
          stream.objectUrl = URL.createObjectURL(stream.mediaSource);
          stream.mediaSource.addEventListener("sourceopen", () => {
            try {
              stream.sourceBuffer = stream.mediaSource.addSourceBuffer(spec.mime);
              stream.sourceBuffer.addEventListener("updateend", () => this.$_pumpAudioQueue(stream));
              this.$_pumpAudioQueue(stream);
            } catch (e) {
              // e.g. SourceBuffer quota exhausted by leaked MediaSources:
              // degrade to whole-clip blob playback instead of dead air
              console.error("MSE SourceBuffer error:", e);
              try {
                if (stream.mediaSource.readyState === "open") stream.mediaSource.endOfStream();
              } catch (e2) {
                // media source already closed
              }
              stream.chunks = stream.queue.splice(0);
            }
          });
          stream.audio = new Audio(stream.objectUrl);
          this.$_attachAudioHandlers(stream);
        } else {
          // Fallback: accumulate all chunks and play the complete Blob at the end
          console.warn("MediaSource does not support " + spec.mime + " - falling back to whole-clip playback");
          stream.chunks = [];
        }
      },
      $_onAudioStreamChunk(data) {
        const stream = this.audioStream;
        if (!stream) return;
        if (stream.pcm) {
          this.$_schedulePcmChunk(stream, data);
          return;
        }
        if (stream.chunks) {
          stream.chunks.push(data);
          return;
        }
        stream.queue.push(data);
        this.$_pumpAudioQueue(stream);
      },
      $_pcmRate(mime) {
        if (!mime || !mime.startsWith("audio/pcm")) return 0;
        const match = /rate=(\d+)/.exec(mime);
        return match ? parseInt(match[1], 10) : 44100;
      },
      $_schedulePcmChunk(stream, data) {
        const pcm = stream.pcm;
        try {
          if (!pcm.ctx) {
            const Ctx = window.AudioContext || window.webkitAudioContext;
            pcm.ctx = new Ctx({ sampleRate: pcm.rate });
          }
          const ctx = pcm.ctx;
          if (ctx.state === "suspended") ctx.resume().catch(() => {});
          const samples = new Int16Array(data);
          if (!samples.length) return;
          const buffer = ctx.createBuffer(1, samples.length, pcm.rate);
          const channel = buffer.getChannelData(0);
          for (let i = 0; i < samples.length; i++) channel[i] = samples[i] / 32768;
          const source = ctx.createBufferSource();
          source.buffer = buffer;
          source.connect(ctx.destination);
          // The preroll keeps a safety margin; clamping to currentTime heals
          // underruns when chunks arrive slower than playback (RTF > 1).
          const startAt = Math.max(ctx.currentTime + 0.12, pcm.nextTime);
          source.start(startAt);
          pcm.nextTime = startAt + buffer.duration;
          if (!stream.started) {
            stream.started = true;
            const ensureCompletion = () => {
              if (this.audioStream !== stream || stream.confirmedPlaying) return;
              stream.confirmedPlaying = true;
              this.$_scheduleStreamCompletion(stream);
            };
            if (ctx.state === "running") {
              ensureCompletion();
            } else {
              // Autoplay blocked: retry the resume on the next user gesture
              document.addEventListener("pointerdown", () => {
                if (this.audioStream === stream && stream.pcm && stream.pcm.ctx) {
                  stream.pcm.ctx.resume().then(ensureCompletion).catch(() => {});
                }
              }, { once: true });
            }
          }
        } catch (e) {
          console.error("PCM scheduling error:", e);
        }
      },
      $_pumpAudioQueue(stream) {
        if (!stream.sourceBuffer || stream.sourceBuffer.updating) return;
        if (stream.queue.length > 0) {
          try {
            stream.sourceBuffer.appendBuffer(stream.queue.shift());
          } catch (e) {
            console.error("appendBuffer error:", e);
            return;
          }
          if (!stream.started) {
            stream.started = true;
            this.$_playAudioElement(stream);
          }
        } else if (stream.ended) {
          try {
            // An explicit finite duration makes the element fire 'ended' reliably
            if (stream.sourceBuffer.buffered.length > 0) {
              stream.mediaSource.duration = stream.sourceBuffer.buffered.end(stream.sourceBuffer.buffered.length - 1);
            }
            if (stream.mediaSource.readyState === "open") stream.mediaSource.endOfStream();
          } catch (e) {
            // media source already closed
          }
        }
      },
      $_endAudioStream(spec) {
        const stream = this.audioStream;
        if (!stream || stream.id !== spec.id) return;
        if (spec.aborted) {
          this.$_stopAudioStream();
          return;
        }
        stream.ended = true;
        if (stream.pcm) {
          this.$_scheduleStreamCompletion(stream);
          return;
        }
        if (stream.chunks) {
          const blob = new Blob(stream.chunks, { type: stream.mime });
          stream.objectUrl = URL.createObjectURL(blob);
          stream.audio = new Audio(stream.objectUrl);
          this.$_attachAudioHandlers(stream);
          this.$_playAudioElement(stream);
          return;
        }
        this.$_pumpAudioQueue(stream);
      },
      $_playAudioElement(stream) {
        if (!stream.audio) return;
        stream.audio.play().then(() => {
          stream.confirmedPlaying = true;
          this.$_scheduleStreamCompletion(stream);
        }).catch(() => {
          console.warn("Audio autoplay blocked - will retry on next user interaction");
          const retry = () => {
            if (this.audioStream === stream && stream.audio) {
              stream.audio.play().then(() => {
                stream.confirmedPlaying = true;
                this.$_scheduleStreamCompletion(stream);
              }).catch(() => {});
            }
          };
          document.addEventListener("pointerdown", retry, { once: true });
        });
      },
      $_scheduleStreamCompletion(stream) {
        // With MediaSource the 'ended' event is not always fired (duration stays
        // Infinity while appending and the final timeupdate lands before the end),
        // so guarantee the completion ack with a timer once duration is known.
        // onended/onerror remain the instant fast paths when the browser fires them.
        // The PCM path has no audio element: poll the AudioContext clock instead.
        if (stream.completionTimer) return;
        const check = () => {
          stream.completionTimer = null;
          if (this.audioStream !== stream) return;
          if (stream.pcm) {
            if (!stream.pcm.ctx) {
              // no chunk ever arrived - nothing to play, ack immediately
              this.$_notifyPlaybackFinished(stream);
              return;
            }
            if (!stream.ended) {
              // more audio may still arrive
              stream.completionTimer = setTimeout(check, 250);
              return;
            }
            const remaining = Math.max(0, stream.pcm.nextTime - stream.pcm.ctx.currentTime) * 1000 + 400;
            stream.completionTimer = setTimeout(() => this.$_notifyPlaybackFinished(stream), remaining);
            return;
          }
          if (!stream.audio) return;
          const audio = stream.audio;
          let end = isFinite(audio.duration) && audio.duration > 0 ? audio.duration : 0;
          if (end === 0 && stream.sourceBuffer && stream.sourceBuffer.buffered.length > 0) {
            end = stream.sourceBuffer.buffered.end(stream.sourceBuffer.buffered.length - 1);
          }
          if (end <= 0) {
            // duration not known yet - retry shortly
            stream.completionTimer = setTimeout(check, 250);
            return;
          }
          const remaining = Math.max(0, end - audio.currentTime) * 1000 + 400;
          stream.completionTimer = setTimeout(() => this.$_notifyPlaybackFinished(stream), remaining);
        };
        check();
      },
      $_attachAudioHandlers(stream) {
        stream.audio.onended = () => this.$_notifyPlaybackFinished(stream);
        stream.audio.onerror = () => this.$_notifyPlaybackFinished(stream);
      },
      $_notifyPlaybackFinished(stream) {
        if (this.audioStream !== stream) return;
        this.audioStream = null;
        if (stream.objectUrl) URL.revokeObjectURL(stream.objectUrl);
        if (stream.completionTimer) clearTimeout(stream.completionTimer);
        // Close the MediaSource so its SourceBuffer is released; without
        // this every completed MSE stream leaked an open MediaSource until
        // GC caught up, and repeated streams exhausted the browser quota
        try {
          if (stream.mediaSource && stream.mediaSource.readyState === "open") {
            stream.mediaSource.endOfStream();
          }
        } catch (e) {
          // media source already closed
        }
        try {
          if (stream.pcm && stream.pcm.ctx) stream.pcm.ctx.close();
        } catch (e) {
          // audio context already closed
        }
        fetch("/api/hooks/tts_playback_finished", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: "{}",
        }).catch((e) => console.warn("playback ack failed:", e));
      },
      toggleHeaderExpansion(expanded) {
        console.log("Toggling header expansion:", expanded);
        this.headerExpanded = expanded;
        // Optionally trigger any other UI updates needed
      },
      handleIncomingMessage(event) {
        console.log("APP received message from backend:", event.data);
      },
      showAutocomplete(event) {
        this.changeView("autocomplete");
      },
      async changeView(view) {
        console.log("Switching view to " + view);
        if (!this.pywebviewready) {
          console.log("Waiting for pywebview to be ready...");
          return;
        }
        this.lastview = this.appview;
        this.appview = view;

        if (view === "onboarding") {
          console.warn("Forcing onboarding");
          const backendApi = await backendApiPromise;
          await backendApi.forceOnboarding();
        } else {
          const backendApi = await backendApiPromise;
          await backendApi.changeView(this.lastview, view);
        }
      },
      maximize() {
        console.log("MAXIMIZE WINDOW");
        backendApiPromise.then((api) => api.maximize());
        this.minimized = false;
        console.log("MINIMIZED=" + this.minimized);
      },
      minimize() {
        console.log("MINIMIZE WINDOW");
        backendApiPromise.then((api) => api.minimize());
        this.minimized = true;
        console.log("MINIMIZED=" + this.minimized);
      },
      goBack() {
        this.appview = this.lastview;
      },
      handleFooterShrink(shrink) {
        this.footerShrink = shrink;
      },
      toggleBootNotReady() {
        if (!this.bootProgressVisible) {
          return;
        }
        this.bootNotReadyVisible = !this.bootNotReadyVisible;
      },
      updateBootProgress(message) {
        const total = Number(message.total || 0);
        const ready = Number(message.ready || 0);
        const notReady = Array.isArray(message.not_ready) ? message.not_ready : [];
        if (!total) {
          return;
        }
        this.bootTotal = total;
        this.bootReady = Math.min(total, Math.max(0, ready));
        this.bootNotReady = notReady;
        if (!this.bootProgressVisible) {
          this.bootProgressVisible = true;
          this.bootProgressFaded = false;
        }
        if (!this.bootProgressHideTimer) {
          this.bootProgressHideTimer = setTimeout(() => {
            this.bootProgressFaded = true;
            setTimeout(() => {
              this.bootProgressVisible = false;
            }, 800);
          }, 600000);
        }
        if (this.bootReady >= this.bootTotal) {
          this.bootProgressFaded = true;
          this.bootNotReadyVisible = false;
          setTimeout(() => {
            this.bootProgressVisible = false;
            // Boot overlay is now hidden — let components do post-boot work
            // (autocomplete focuses its input so the OS keyboard opens at boot).
            window.dispatchEvent(new Event("boot-complete"));
          }, 1200);
        }
      },
    },
  });
  console.log("created");
  app = app.mount("#app");
  if (typeof window !== "undefined") {
    window.app = { ...window.app, ...app };
    registerReadypy(app.readypy.bind(app));
  }
  console.log(app);
}
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initializeApp, { once: true });
} else {
  initializeApp();
}
