<template>
    <span class="example">{{ msg }}</span>
  </template>
  <script>
    export default {
      data () {
        return {
          msg: 'Second!',
          color: 'red',
        }
      }
    }
  </script>
  
  <style scoped>
    .example {
      color: v-bind('color');
    }
  </style>  