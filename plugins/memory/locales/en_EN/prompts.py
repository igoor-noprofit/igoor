prompts = {
    "memory": {
        "system": """<instructions>You must analyze a conversation to extract possible memories:

- Short-term memory: Recent or one-off events.
- Long-term memory: Preferences, constant facts, life memories.

In the conversation, Q: is the interlocutor, R: is the user (named {bio_name}).
Return a JSON with:

"theme": summarize the theme of the conversation;
"facts": an array containing all relevant information about {bio_name}, their family, friends, preferences (food, politics, arts, etc.), life memories. For each fact, specify whether it is short-term or long-term. There may be no facts to save.
"tags": labels to classify the conversation and make it easier to find later.

Important criteria:
<criteria>
- A "fact" is an objective and verifiable piece of information about the user or their circle.
- Facts must be explicitly stated or obviously deduced from the conversation.
- Exhaustiveness and Precision: When several related details are provided on the same subject (e.g., a list of names, several characteristics of an object, the ingredients of a favorite recipe), consolidate this information into a single complete and precise fact. Avoid fragmenting information that is naturally unified in the conversation.
- Temporary or contextual opinions are not long-term facts, unless they reveal a persistent preference or state.
- If information is uncertain or non-essential, do not consider it a fact.
- The "fact" must be formulated in an atomic but complete way.
</criteria>

Here are some examples of prompts and the requested JSON output:

<examples>
Input: Q: The weather is nice today. R: Absolutely.
Output: {{"theme": "weather", "tags": ["nice weather"], "facts": []}}

Input: Q: Are you thirsty? R: Yes. Q: Do you want some water? R: With pleasure.
Output: {{"theme": "thirst", "tags": ["water"], "facts": []}}

Input: Q: Do you want a snack? R: Yes, a yogurt. Q: Plain or with fruit? R: Plain, with a bit of sugar.
Output: {{"theme":"snack","tags":["yogurt","food preferences"],"facts":[{{"fact":"{bio_name} wants a plain yogurt with a bit of sugar for snack","type":"short"}}]}}

Input: R: Can you close the window? You know I'm sensitive to cold. Q: No problem!
Output: {{"theme": "cold", "facts" : [{{"fact":"{bio_name} is sensitive to cold"]}}

Input: Q: Do you like rice pudding? R: I don't like it at all! Q: I thought you liked it! R: I don't anymore!
Output: {{"theme":"rice pudding","facts":[{{"fact":"{bio_name} no longer likes rice pudding","type":"long"}}],"tags":["Food preferences","cake","dessert"]}}

Input: Q: Have you heard from Anatole? R: Yes, he returned to Paris Q: Is he well? R: Yes
Output: {{"theme":"family","tags":["Anatole","Paris","children"],"facts":[{{"fact":"Anatole returned to Paris","type":"short"}},{{"fact":"Anatole is well","type":"short"}}]}}

Input: Q: How many children do you have? R: I have three children Q: What are their names? R: Anton, Paloma and Anatole!
Output: {{"theme":"family","tags":["children","family","Anton","Paloma","Anatole"],"facts":[{{"fact":"{bio_name} has three children: Anton, Paloma and Anatole","type":"long"}}]}}

Input : Q: He told me Claire doesn't blame you anymore R: Are you sure? Q: Yes R: I'm very relieved
Output : {{"theme":"family relations","tags":["Claire","family"],"facts":[{{"fact":"Claire doesn't blame him/her anymore","type":"short"}},{{"fact":"{bio_name} is very relieved that Claire doesn't blame him/her anymore","type":"short"}}]}}
</examples>

Attention: opinions expressed by the user are preceded by R:, not by Q:. For example:

<example>
Input: Q: I like ice cream
Output: {{"theme":"food preferences","tags":["ice cream"],"facts":[]}}
</example>

However:

<example>
Q: I like ice cream R: Me too!
Output: {{"theme":"food preferences","tags":["ice cream"],"facts":[{{"fact":"{bio_name} likes ice cream","type":"long"}}]}}
</example>

Also, questions asked by the interlocutor that remain unanswered are NOT memories:

<example>
Input: Q: Do you like spaghetti?
Output: {{"theme":"food preferences","tags":["spaghetti"],"facts":[]}}
</example>

Return only the facts and opinions in JSON format, without any explanation.
</instructions>
""",
        "usr": """<conversation>
        {conversation}
        </conversation>"""
    },
    "memory_review": {
        "system": """<instructions>You receive a JSON with:

1) a conversation analyzed by the AI to extract short- and long-term memories;
2) the long-term memory detected by the AI.

<example>
{
    "conversation": " Q: Do you like rice pudding? R: I don't like it at all! Q: I thought you liked it! R: I don't anymore ,!",
    "memory": {
        "fact": "{bio_name} no longer likes rice pudding",
        "type": "long"
    },
    "rag":"---{bio_name} likes Asian dishes, especially soups"
}
</example>

In the conversation, Q: is the interlocutor, R: is the user (named {bio_name}).
In this example, the AI rightly recognizes that a new long-term memory should be saved,
because a change in the user's preferences has been detected.
Also, the information already in the knowledge base (rag) does NOT already indicate this info.

The AI detects the information to memorize according to these criteria:

<criteria>
- "fact" is relevant information about the user, their family, friends, preferences (food, politics, arts, etc.)
- A "fact" is an objective and verifiable piece of information about the user or their circle or "stable" opinions of the user
- Facts must be explicitly stated or obviously deduced from the conversation.
- Temporary or contextual opinions are not long-term facts, unless they reveal a persistent preference or state.
- If information is uncertain or non-essential, do not consider it a fact
- Short-term memory: Recent or one-off events.
- Long-term memory: Preferences, constant facts, life memories.
</criteria>

Example of validated memory output:

<example>
{{"valid":true,"reason":"A change in {bio_name}'s preferences has been detected"}}
</example>

The "reason" field must indicate why the memory is validated.
The memory can be validated even if the RAG already contains a different complementary piece of information (e.g. "likes rice" is compatible with "likes spaghetti").

---
The memory is NOT validated:

1) if the information does not constitute a long-term memory
2) if the RAG already contains identical or very similar information, or if the RAG contains more complete or more specific information that makes the new 'fact' redundant or less informative.

Furthermore, to be validated, the extracted information ("fact") must be **clear and specific**, with a **clearly defined subject**. Ambiguous memories or those lacking essential details should not be validated. For example, avoid validating facts such as:

- "Igor thinks the software is the best for free photorealistic rendering" (Which software are we talking about?)
- "The interlocutor likes Easter Island" (Who is the interlocutor?)

Make sure the subject of the information is explicitly mentioned and that key details
(such as the name of the software, or the identity of the person) are present in the "fact".

Examples of validation and non-validation:

<examples>
Input:
{
    "conversation": " R: I am sensitive to certain flavors? Q: Which ones? R: There are many.",
    "memory": {
        "fact": "{bio_name} is sensitive to many flavors",
        "type": "long"
    }
}
Output:
{{"valid":false,"reason":"We do not know which flavors {bio_name} is sensitive to"}}

Input:
{
    "conversation": " R: I am sensitive to very spicy flavors?",
    "memory": {
        "fact": "{bio_name} is sensitive to very spicy flavors",
        "type": "long"
    }
}
Output:
{{"valid":true,"reason":"This preference is clear and specific"}}

Input:
{
    "conversation": " Q: Do you want us to make a soup tonight? R: Yes, a vegetable soup. Q: With croutons? R: Yes, and a bit of grated cheese.",
    "memory": {
        "fact": "{bio_name} likes croutons in their soup",
        "type": "long"
    },
    "rag": "---{bio_name} likes Asian dishes---"
}
Output:
{{"valid":false,"reason":"We do not know if {bio_name} generally likes croutons in their soup or if they just wanted to try it"}}

Input:
{
    "conversation": "R: do you like jazz?",
    "memory": {
        "fact": "{bio_name} likes jazz",
        "type": "long"
    }
}
Output:
{{"valid":false,"reason":"The question is not clear and the user did not answer"}}

Input:
{
    "conversation": "Q: I like jazz more and more",
    "memory": {
        "fact": "{bio_name} likes jazz",
        "type": "long"
    },
    "rag": "---Artistic preferences of {bio_name}: loves jazz---"
}
Output:
{{"valid":false,"reason":"This is already established in their artistic preferences, no need to repeat"}}

Input:
{
    "conversation": "Q:  How many children do you have? R: I have three children, Anton, Paloma and Anatole!",
    "memory": {
        "fact": "{bio_name} has a son or daughter named Anatole",
        "type": "long"
    },
    "---family: {bio_name}'s children are called Anton, Paloma and Anatole [children, Anton, Paloma, Anatole]---"
}
Output:
{{"valid":false,"reason":"The information that {bio_name} has three children (Anton, Paloma, Anatole) is already present in the RAG and is more complete than the proposed fact about only Anatole."}}
</examples>
</instructions>
""",
        "usr": """<memory_to_be_checked>
        {memory_to_be_checked}
        </memory_to_be_checked>"""
    }
}