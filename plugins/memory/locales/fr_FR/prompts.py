prompts = {
    "memory": {
        "system": """<instructions>Tu dois analyser une conversation pour en extraire d'éventuelles mémoires: 

- Mémoire à court terme : Événements récents ou ponctuels.
- Mémoire à long terme : Préférences, faits constants, souvenirs de vie.

Dans la conversation, Q: est l'interlocuteur, R: est l'utilisateur (nommé {bio_name}). 
Retourne un JSON avec:

"theme": synthétise le thème de la conversation; 
"facts": un array contenant toutes les informations pertinentes sur {bio_name}, sa famille,ses amis,ses préférences (alimentaires, politiques,artistiques etc.), les souvenirs de sa vie. Pour chaque fact, précise s'il s'agit d'une information de court terme ou de long terme.Il peut ne pas y avoir des faits à sauvegarder.
"tags": étiquettes pour classer la conversation et la mieux la retrouver ensuite.

Critères importants : 
<criteria>
- Un "fact" est une information objective et vérifiable concernant l'utilisateur ou son entourage.
- Les faits doivent être explicitement exprimés ou déduits de manière évidente dans la conversation.
- Exhaustivité et Précision: Lorsque plusieurs détails liés sont fournis pour un même sujet (par exemple, une liste de noms, plusieurs caractéristiques d'un objet, les ingrédients d'une recette aimée), consolider ces informations en un seul fait complet et précis.Éviter de fragmenter une information qui est naturellement unifiée dans la conversation.
- Les opinions temporaires ou contextuelles ne sont pas des faits de long terme, sauf si elles révèlent une préférence ou un état persistant.
- Si une information est incertaine ou non essentielle, ne la considère pas comme un fait.
- Le "fact" doit être formulé de manière atomique mais complète. 
</criteria>

Voici quelques exemples de prompt et de output JSON demandé:

<examples>
Input: Q: Il fait beau aujourd'hui. R: Absolument.
Output: {{"theme": "météo", "tags": ["beau temps"], "facts": []}}

Input: Q: Tu as soif ? R: Oui. Q: Tu veux de l'eau ? R: Avec plaisir.
Output: {{"theme": "soif", "tags": ["eau"], "facts": []}}

Input: Q: Tu veux prendre un goûter ? R: Oui, un yaourt. Q: Nature ou aux fruits ? R: Nature, avec un peu de sucre.
Output: {{"theme":"goûter","tags":["yaourt","préférences alimentaires"],"facts":[{{"fact":"{bio_name} veut un yaourt nature avec un peu de sucre pour le goûter","type":"short"}}]}}

Input: R: Tu peux fermer la fenetre? Tu sais que je suis frileux. Q: No problem!
Output: {{"theme": "froid", "facts" : [{{"fact":"{bio_name} est frileux"]}}

Input: Q: T'aime le gâteau de riz ? R: J'aime pas du tout ! Q: Je pensais que tu l'aimais ! R: Je l'aime plus !
Output: {{"theme":"gâteau de riz","facts":[{{"fact":"{bio_name} n'aime plus le gâteau de riz","type":"long"}}],"tags":["Préférences alimentaires","gâteau","dessert"]}}

Input: Q: Tu as eu des nouvelles d'Anatole ? R: Oui, il est rentré à Paris Q: Il va bien ? R: Oui
Output: {{"theme":"famille","tags":["Anatole","Paris","enfants"],"facts":[{{"fact":"Anatole est rentré à Paris","type":"short"}},{{"fact":"Anatole va bien","type":"short"}}]}}

Input: Q: Combien d'enfants tu as ? R: J'ai trois enfants Q: Comment il s'appellent ? R: Anton, Paloma et Anatole !
Output: {{"theme":"famille","tags":["enfants","famille","Anton","Paloma","Anatole"],"facts":[{{"fact":"{bio_name} a trois enfants : Anton, Paloma et Anatole","type":"long"}}]}}

Input : Q: Il m'a dit que Claire ne t'en veut pas R: T'es sur de ça ? Q: Oui R: J'en suis très soulagé
Output : {{"theme":"relations familiales","tags":["Claire","famille"],"facts":[{{"fact":"Claire n'en veut pas à {bio_name}","type":"short"}},{{"fact":"{bio_name} est très soulagé que Claire ne lui en veut pas","type":"short"}}]}}
</examples>

Attention: les opinions exprimées par l'utilisateur sont précédées par R:, et pas par Q:. Par exemple: 

<example>
Input: Q: J'aime la glace
Output: {{"theme":"préférences alimentaires","tags":["glace"],"facts":[]}}
</example>

En revanche:

<example>
Input: Q: J'aime la glace R: Moi aussi!
Output: {{"theme":"préférences alimentaires","tags":["glace"],"facts":[{{"fact":"{bio_name} aime la glace","type":"long"}}]}}
</example>

Aussi,des questions posées par l'interlocuteur et qui restent sans réponses ne sont PAS des mémoires: 

<example>
Input: Q: Est-ce que tu aime les spaghetti ?
Output: {{"theme":"préférences alimentaires","tags":["spaghetti"],"facts":[]}}
</example>

Retourne seulement les faits et opinions dans le format JSON,sans aucune explication.
</instructions>
""",
        "usr": """<conversation>
        {conversation}
        </conversation>"""
    },
    "memory_review": {
        "system": """<instructions>Tu reçois un JSON avec: 

1) une conversation analysée par l'IA pour en extraire des mémoires de court et de long terme;
2) la mémoire de long terme que l'IA a détecté.

<example>
{{
    "conversation": " Q: T'aimes le gâteau de riz ? R: J'aime pas du tout ! Q: Je pensais que tu l'aimais ! R: Je l'aime plus ,!",
    "memory": {{
        "fact": "{bio_name} n'aime plus le gâteau de riz",
        "type": "long"
    }},
    "rag":"---{bio_name} aime les plats asiatiques,en particulier les soupes"
}}
</example>

Dans la conversation, Q: est l'interlocuteur, R: est l'utilisateur (nommé {bio_name}). 
Dans cet exemple, l'IA reconnait justement qu'un nouvelle mémoire à long terme est à sauvegarder, 
parce qu'une évolution des préférences de l'utilisateur a été détecté.
Aussi,les informations déjà dans la base de connaissances (rag) n'indiquent PAS déjà cette info.

L'IA a détecte l'information à mémoriser selon ces critères:

<criteria>
- "fact" est une information pertinente sur l'utilisateur,sa famille,ses amis,ses préférences (alimentaires, politiques,artistiques etc.)
- Un "fact" est une information objective et vérifiable concernant l'utilisateur ou son entourage ou des opinions "stables" de l'utilisateur
- Les faits doivent être explicitement exprimés ou déduits de manière évidente dans la conversation.
- Les opinions temporaires ou contextuelles ne sont pas des faits de long terme, sauf si elles révèlent une préférence ou un état persistant.
- Si une information est incertaine ou non essentielle, ne la considère pas comme un fait
- Mémoire à court terme : Événements récents ou ponctuels.
- Mémoire à long terme : Préférences, faits constants, souvenirs de vie.
</criteria>

Exemple de output de mémoire validée:

<example>
{{"valid":true,"reason":"Une évolution des préférences de {bio_name} a été détecté"}}
</example>

Le champ "reason" DOIT indiquer la raison pour laquelle la mémoire est validée.
La mémoire peut etre validée meme si le RAG contient déjà une info complémentaire différente (ex. "aime le riz" est compatible avec "aime les spaghetti").

---
La mémoire n'est PAS validée:

1)si l'information ne constitue pas une mémoire de long terme
2)si le RAG contient déjà une information identique, très semblable, ou si le RAG contient une information plus complète ou plus spécifique qui rend le nouveau 'fact' redondant ou moins informatif.

De plus, pour être validée, l'information extraite ("fact") doit être **claire et spécifique**, avec un **sujet clairement défini**. Les mémoires ambiguës ou manquant de détails essentiels ne doivent pas être validées. Par exemple, évitez de valider des faits tels que :

- "Igor pense que le logiciel est le meilleur pour des rendus photoréalistes gratuits" (De quel logiciel on parle?)
- "L'interlocuteur aime l'île de Pâques" (Qui est l'interlocuteur ?)

Assurez-vous que le sujet de l'information est explicitement mentionné et que les détails clés 
(comme le nom du logiciel,ou l'identité de la personne) sont présents dans le "fact".   

Exemples de validation et de non validation:

<examples>
Input: 
{{
    "conversation": " R: Je suis sensible à certaines saveurs ? Q: Lesquelles ? R: Y en a beaucoup.",
    "memory": {{
        "fact": "{bio_name} est sensible à beaucoup de saveurs",
        "type": "long"
    }}
}}
Output:
{{"valid":false,"reason":"Nous ne savons pas à quelles saveurs {bio_name} est sensible"}}

Input: 
{{
    "conversation": " R: Je suis sensible aux saveurs très épicés ?",
    "memory": {{
        "fact": "{bio_name} est sensible aux saveurs très épicés",
        "type": "long"
    }}
}}
Output:
{{"valid":true,"reason":"Cette préférence est claire et spécifique"}}

Input: 
{{
    "conversation": " Q: Tu veux qu'on prépare une soupe ce soir ? R: Oui, une soupe aux légumes. Q: Avec des croûtons ? R: Oui, et un peu de fromage râpé.",
    "memory": {{
        "fact": "{bio_name} aime les croûtons dans sa soupe",
        "type": "long"
    }},
    "rag": "---{bio_name} aime les plats asiatiques---"
}}
Output:
{{"valid":false,"reason":"Nous ne savons pas si {bio_name} en général aime les croutons dans sa soupe ou si il voulait juste essayer"}}

Input: 
{{
    "conversation": "R: que tu aimes le jazz?",
    "memory": {{
        "fact": "{bio_name} aime le jazz",
        "type": "long"
    }}
}}
Output:
{{"valid":false,"reason":"La question n'est pas claire et l'utilisateur n'y a pas répondu"}}

Input: 
{{
    "conversation": "Q: J'aime de plus en plus le jazz",
    "memory": {{
        "fact": "{bio_name} aime le jazz",
        "type": "long"
    }},
    "rag": "---Préférences artistiques de {bio_name}: il adore le jazz---"
}}
Output:
{{"valid":false,"reason":"c'est déjà établi dans ses préférences artistiques, pas besoin de le répéter"}}

Input: 
{{
    "conversation": "Q:  Combien d'enfants tu as ? R: J'ai trois enfants, Anton, Paloma et Anatole !",
    "memory": {{
        "fact": "{bio_name} a un fils ou une fille nommé(e) Anatole",
        "type": "long"
    }},
    "---famille: Les enfants de {bio_name} s'appellent Anton, Paloma et Anatole [enfants, Anton, Paloma, Anatole]---"
}}
Output:
{{"valid":false,"reason":"L'information que {bio_name} a trois enfants (Anton, Paloma, Anatole) est déjà présente dans le RAG et est plus complète que le fait proposé concernant uniquement Anatole."}}
</examples>
</instructions>
""",
        "usr": """<memory_to_be_checked>
        {memory_to_be_checked}
        </memory_to_be_checked>"""
    }
}