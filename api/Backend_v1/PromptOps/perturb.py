import random
import string
import pandas as pd
import pickle
import os
import nltk
from nltk.tokenize import word_tokenize
from nltk.corpus import wordnet
from nltk import pos_tag
from textblob import TextBlob
from PyDictionary import PyDictionary  # Switch back to PyDictionary
import spacy
import openai
import re
import language_tool_python
from nltk.corpus import wordnet as wn
# import coreferee
import requests  # for llama lmstudio llm
import spacy
from spacy.matcher import Matcher
# import neuralcoref
# from PromptOps.act_pas import active_to_passive

nlp = spacy.load("en_core_web_sm")
# nlp.add_pipe("coreferee")

dictionary = PyDictionary()  # Initialize PyDictionary

url = "http://127.0.0.1:8000/v1/chat/completions"


def get_wordnet_pos(treebank_tag):
    """Converts Treebank POS tags to WordNet POS tags."""
    if treebank_tag.startswith('J'):
        return wordnet.ADJ
    elif treebank_tag.startswith('V'):
        return wordnet.VERB
    elif treebank_tag.startswith('N'):
        return wordnet.NOUN
    elif treebank_tag.startswith('R'):
        return wordnet.ADV
    else:
        return wordnet.NOUN  # Default to noun if unknown


def get_past_participle(verb: str) -> str:
    """
    Retrieve the past participle of a given verb.
    This is a simple mapping for common verbs. In a real scenario, we would use an NLP library like NLTK.
    """
    irregular_verbs = {
        "eat": "eaten",
        "see": "seen",
        "write": "written",
        "go": "gone",
        "do": "done",
        "make": "made",
        "play": "played",
        "explain": "explained",
        "clean": "cleaned",
        "love": "loved"
    }
    return irregular_verbs.get(verb, verb + "ed")


def active_to_passive(sentence: str) -> str:
    """
    Convert an active voice sentence to passive voice if found in dataset, otherwise, use algorithmic conversion.

    Args:
        sentence (str): Active voice sentence.

    Returns:
        str: Converted passive voice sentence or a message if conversion is not possible.
    """
    # Load dataset
    file_path = os.path.join(os.path.dirname(
        __file__), "active_to_passive_dataset.csv")
    df = pd.read_csv(file_path)

    sentence = sentence.strip()

    # Check if the sentence exists in the dataset
    match = df[df["input"].str.strip().str.lower() == sentence.lower()]
    if not match.empty:
        passive_sentence = match["output"].values[0].replace("Passive: ", "")
        if passive_sentence.lower() == sentence.lower():
            return "Could not convert to passive voice."
        return passive_sentence

    # Handle cases that cannot be converted to passive voice
    if re.match(r'^(Are|Am|Is)\\s+', sentence, re.IGNORECASE):
        return "Could not convert to passive voice."

    if re.match(r'^(She|He|They|We|I)\\s+(has|have|is|are|was|were)\\s+\\w+', sentence, re.IGNORECASE):
        return "Could not convert to passive voice."

    if re.match(r'^(This|That|It)\\s+is\\s+\\w+', sentence, re.IGNORECASE):
        return "Could not convert to passive voice."

    # Handle exceptional case where verb is 'related'
    if re.match(r'^Are more people today related to (.+?) than (.+?)\\?$', sentence, re.IGNORECASE):
        return "Could not convert to passive voice."

    # Match question structure
    question_match = re.match(
        r'^(Will|Do|Does|Did|Could|Can|Might|Should|Would|Must|Shall|Has|Have|Had|Where|When|Why|How)\\s+(.*?)\\s+(\\w+)\\s+(.*?)\\?$', sentence, re.IGNORECASE)

    if question_match:
        aux, subject, verb, obj = question_match.groups()

        # Ensure correct verb transformation
        if verb.endswith("s"):
            verb = verb[:-1]
        past_participle = get_past_participle(verb)

        # Adjust subject pronouns
        subject_map = {"I": "me", "he": "him",
                       "she": "her", "they": "them", "we": "us"}
        subject = subject_map.get(subject.lower(), subject)

        # Handle auxiliary verb agreement for different tenses
        aux_map = {"do": "is", "does": "is", "did": "was", "has": "has been", "have": "have been", "had": "had been", "will": "will be",
                   "can": "can be", "could": "could be", "might": "might be", "should": "should be", "must": "must be", "shall": "shall be"}
        aux = aux_map.get(aux.lower(), aux)

        # Identify and preserve time indicators
        time_indicators = ["today", "yesterday", "tomorrow", "soon",
                           "now", "next week", "last year", "earlier", "later", "by"]
        obj_tokens = obj.split()
        time_words = [word for word in obj_tokens if word.lower()
                      in time_indicators]
        obj = " ".join(
            [word for word in obj_tokens if word.lower() not in time_indicators])

        # Construct passive sentence
        passive_sentence = f"{aux} {obj} be {past_participle} by {subject}"

        # Ensure only one occurrence of time indicators, placed at the end
        if time_words:
            passive_sentence += " " + " ".join(time_words[-1:])

        passive_sentence += "?"
        if passive_sentence.lower() == sentence.lower():
            return "Could not convert to passive voice."
        return passive_sentence.capitalize()

    return "Could not convert to passive voice."


def get_synonym(word, pos):
    """Fetches a synonym for a given word based on its POS tag using WordNet."""
    synonyms = set()

    # Map NLTK POS tags to WordNet POS tags
    wn_pos_map = {
        'NN': wn.NOUN, 'NNS': wn.NOUN, 'NNP': wn.NOUN, 'NNPS': wn.NOUN,  # Nouns
        'VB': wn.VERB, 'VBD': wn.VERB, 'VBG': wn.VERB, 'VBN': wn.VERB, 'VBP': wn.VERB, 'VBZ': wn.VERB,  # Verbs
        'JJ': wn.ADJ, 'JJR': wn.ADJ, 'JJS': wn.ADJ,  # Adjectives
        'RB': wn.ADV, 'RBR': wn.ADV, 'RBS': wn.ADV   # Adverbs
    }

    # Get WordNet POS type if available
    wn_pos = wn_pos_map.get(pos, None)

    # Fetch synonyms if a valid POS is found
    if wn_pos:
        for syn in wn.synsets(word, pos=wn_pos):
            for lemma in syn.lemmas():
                if lemma.name() != word.replace("_", " "):  # Exclude original word
                    # Replace underscores with spaces
                    synonyms.add(lemma.name().replace("_", " "))

    # Return synonym if found, else original word
    return random.choice(list(synonyms)) if synonyms else word


class Perturbation:
    def __init__(self):
        # self.nlp = spacy.load("en_core_web_sm") small model

        self.nlp = spacy.load("en_core_web_lg")
        # coreferee.add_to_pipe(self.nlp)
        self.dictionary = PyDictionary()
        self.nlp.add_pipe("coreferee")

    def robust(self, text):
        """
        Swap one random character with its neighbor in each word only once.
        Prevents swapping punctuation such as ','.
        Return a list of sentences where each word is swapped randomly once.
        """
        words = text.split()  # Split the text into words
        perturbed_sentences = []  # List to store sentences with perturbed words

        for word_index, word in enumerate(words):
            if len(word) < 2:
                continue  # Skip words too short to swap

            # Ensure the word does not end with punctuation (e.g., ',')
            if word[-1] in string.punctuation:
                core_word = word[:-1]  # Exclude the punctuation
                punctuation = word[-1]
            else:
                core_word = word
                punctuation = ''

            # Choose a random index to swap characters in the core word
            swap_index = random.randint(0, len(core_word) - 2)
            perturbed_word = (
                core_word[:swap_index] +
                core_word[swap_index + 1] +
                core_word[swap_index] +
                core_word[swap_index + 2:]
            )

            # Reattach punctuation if it exists
            perturbed_word += punctuation

            # Create a new sentence with the perturbed word
            new_sentence = words[:word_index] + \
                [perturbed_word] + words[word_index + 1:]
            perturbed_sentences.append(' '.join(new_sentence))

        return perturbed_sentences

    # def robust(self, text):
    #     """
    #     Swap one random character with its neighbor in each word only once.
    #     Return a list of sentences where each word is swapped randomly once.
    #     """
    #     words = text.split()  # Split the text into words
    #     perturbed_sentences = []  # List to store sentences with perturbed words

    #     for word_index, word in enumerate(words):
    #         if len(word) < 2:
    #             continue  # Skip words too short to swap

    #         # Choose a random index to swap characters in the word
    #         swap_index = random.randint(0, len(word) - 2)
    #         perturbed_word = (
    #             word[:swap_index] +
    #             word[swap_index + 1] +
    #             word[swap_index] +
    #             word[swap_index + 2:]
    #         )

    #         # Create a new sentence with the perturbed word
    #         new_sentence = words[:word_index] + [perturbed_word] + words[word_index + 1:]
    #         perturbed_sentences.append(' '.join(new_sentence))

    #     return perturbed_sentences

    def process_questions(self, df, question_column, expected_answer_column):
        """
        Processes the dataset, applies perturbations to each question, and matches with the expected answers.

        Args:
            df (pd.DataFrame): Input dataframe with columns containing questions and expected answers.
            question_column (str): Column name containing the questions.
            expected_answer_column (str): Column name containing the expected answers.

        Returns:
            pd.DataFrame: A new dataframe with the original question, perturbations, and expected answers.
        """
        # Initialize lists to store results
        rows = []

        for index, row in df.iterrows():
            question = row[question_column]
            expected_answer = row[expected_answer_column]

            # Generate perturbations using the robust method
            perturbed_set = self.robust(question)

            # Add each perturbation as a new row in the output
            for i, perturbation in enumerate(perturbed_set, start=1):
                rows.append({
                    "Original_Question_Index": index,
                    "Original_Question": question,
                    # Ensure unique naming
                    "Perturbation": f"Perturb {index}-{i}",
                    "Perturbed_Question": perturbation,
                    "Expected_Answer": expected_answer
                })

        # Convert to DataFrame
        result_df = pd.DataFrame(rows)
        return result_df

    # def get_synonym(self, word, pos_tag):
    #     """
    #     Retrieve a synonym for the given word and part-of-speech (POS) tag.
    #     If no synonym is found, return the original word.
    #     """
    #     pos_map = {
    #         'JJ': wordnet.ADJ,    # Adjectives
    #         'JJR': wordnet.ADJ,
    #         'JJS': wordnet.ADJ,
    #         'RB': wordnet.ADV,    # Adverbs
    #         'RBR': wordnet.ADV,
    #         'RBS': wordnet.ADV,
    #         'VB': wordnet.VERB,   # Verbs
    #         'VBD': wordnet.VERB,
    #         'VBG': wordnet.VERB,
    #         'VBN': wordnet.VERB,
    #         'VBP': wordnet.VERB,
    #         'VBZ': wordnet.VERB,
    #         'NN': wordnet.NOUN,   # Nouns
    #         'NNS': wordnet.NOUN,
    #         'NNP': wordnet.NOUN,
    #         'NNPS': wordnet.NOUN,
    #     }

    #     wn_pos = pos_map.get(pos_tag, wordnet.NOUN)  # Default to NOUN if not found

    #     synonyms = wordnet.synsets(word, pos=wn_pos)
    #     if not synonyms:
    #         return word

    #     synonym_words = set(
    #         lemma.name().replace('_', ' ') for synset in synonyms for lemma in synset.lemmas()
    #         if lemma.name().lower() != word.lower()
    #     )
    #     return random.choice(list(synonym_words)) if synonym_words else word

    # def taxonomy(self, sentence):
    #     tokens = word_tokenize(sentence)
    #     tagged = pos_tag(tokens)

    #     # Replace adjectives or adverbs with synonyms
    #     new_tokens = [
    #         self.get_synonym(word, tag) if tag in ['JJ', 'JJR', 'JJS', 'RB', 'RBR', 'RBS'] else word
    #         for word, tag in tagged
    #     ]

    #     new_sentence = ' '.join(new_tokens)
    #     return new_sentence

    def taxonomy(self, sentence):
        """Replaces words in a sentence with their synonyms (if available)."""
        # Tokenize and tag the sentence
        tokens = word_tokenize(sentence)
        tagged = pos_tag(tokens)

        new_tokens = []
        modified = False

        # Iterate over each word and attempt to replace it with a synonym
        for word, tag in tagged:
            synonym = get_synonym(word, tag)  # Fetch a synonym
            if synonym != word:  # If a replacement occurred
                modified = True
            new_tokens.append(synonym)

        # Reconstruct the sentence
        new_sentence = ' '.join(new_tokens)

    # def negation(self, text):
    #     """
    #     Replaces occurrences of "n't" or "not" with their antonym transformations.
    #     For example:
    #     - Input: "The food is not bad"
    #     - Output: "The food is good"
    #     """
    #     def antonyms_for(word):
    #         """
    #         Find antonyms for a given word across all parts of speech.

    #         :param word: The word for which to find antonyms.
    #         :return: A set of antonyms for the given word.
    #         """
    #         antonyms = set()
    #         for ss in wn.synsets(word):
    #             for lemma in ss.lemmas():
    #                 for antonym in lemma.antonyms():
    #                     antonyms.add(antonym.name())
    #         return antonyms

    #     # Tokenize the text
    #     tokens = word_tokenize(text)
    #     tagged = pos_tag(tokens)  # POS tagging for identifying parts of speech

    #     # Process tokens to handle "not" or "n't"
    #     result = []
    #     skip_next = False  # To handle the word after "not" or "n't"

    #     for i, (word, tag) in enumerate(tagged):
    #         if skip_next:  # Skip the next word after processing "not" or "n't"
    #             skip_next = False
    #             continue

    #         if word.lower() in ["not", "n't"]:  # Handle negations
    #             # Find antonyms for the word after "not" or "n't"
    #             if i + 1 < len(tagged):  # Check if there is a next word
    #                 next_word, next_tag = tagged[i + 1]
    #                 antonyms = antonyms_for(next_word)
    #                 if antonyms:  # Use the first antonym found
    #                     result.append(list(antonyms)[0])
    #                 else:  # If no antonym is found, keep the original word
    #                     result.append(next_word)
    #                 skip_next = True  # Skip the next word as it's already processed
    #         else:
    #             result.append(word)

    #     # Join tokens and fix spaces before punctuation
    #     transformed_text = " ".join(result)
    #     transformed_text = re.sub(r'\s+([?.!,"])', r'\1', transformed_text)  # Fix spaces before punctuation
    #     return transformed_text

    def negation(self, text):
        """
        Modifies the sentence to negate its meaning:

        - If "not" or "n't" is present, replaces the next adjective or adverb with its antonym (if available).
        - If "not" or "n't" is absent, inserts "not" before an adjective or adverb and replaces it with its antonym.
        - Does NOT remove or modify verbs.

        :param text: The input sentence.
        :return: A negated version of the sentence.
        """
        def antonyms_for(word):
            """
            Find antonyms for a given word across all parts of speech.

            :param word: The word for which to find antonyms.
            :return: A set of antonyms for the given word.
            """
            antonyms = set()
            for ss in wn.synsets(word):
                for lemma in ss.lemmas():
                    for antonym in lemma.antonyms():
                        antonyms.add(antonym.name())
            return antonyms
        tokens = word_tokenize(text)
        tagged = pos_tag(tokens)

        result = []
        skip_next = False  # Flag to skip the next word after negation handling
        negation_found = False

        for i, (word, tag) in enumerate(tagged):
            if skip_next:
                skip_next = False
                continue

            # Handle existing negation by replacing the next adjective/adverb with its antonym
            if word.lower() in ["not", "n't"]:
                if i + 1 < len(tagged):
                    next_word, next_tag = tagged[i + 1]
                    if next_tag.startswith(("JJ", "RB")):  # Adjectives, adverbs
                        antonyms = antonyms_for(next_word)
                        if antonyms:
                            result.append(list(antonyms)[0])
                        else:
                            result.append(next_word)
                        skip_next = True
                negation_found = True
            else:
                result.append(word)

        # If no negation was found, add "not" before an adjective or adverb
        if not negation_found:
            for i, (word, tag) in enumerate(tagged):
                if tag.startswith(("JJ", "RB")):  # Adjectives, adverbs (not verbs)
                    antonyms = antonyms_for(word)
                    if antonyms:
                        result.insert(i, "not")
                        result[i + 1] = list(antonyms)[0]
                        break  # Only add negation once

        # Join tokens and fix spacing
        transformed_text = " ".join(result)
        transformed_text = re.sub(r'\s+([?.!,"])', r'\1', transformed_text)

        return transformed_text

    def coreference(self, text):
        """
        Resolves coreferences in the given text using the loaded NLP model with coreference resolution capabilities.

        Args:
            text (str): The input text to process.

        Returns:
            str: The text with resolved coreferences.
        """
        try:
            # Process the text with the NLP model
            doc = self.nlp(text)

            # If no coreference chains exist, return the original text
            if not doc._.coref_chains:
                return text

            # Use coreference chains to resolve references
            resolved_text = []
            for token in doc:
                if token.is_punct:
                    # Preserve punctuation as-is
                    resolved_text.append(token.text)
                else:
                    # Attempt to resolve the token
                    resolved_token = doc._.coref_chains.resolve(token)
                    if resolved_token:
                        # Use the first resolved token's text
                        resolved_text.append(resolved_token[0].text)
                    else:
                        # Use the original token if no resolution exists
                        resolved_text.append(token.text)

            # Join resolved text and fix spacing around punctuation
            resolved_text = " ".join(resolved_text)
            # Fix spaces before punctuation
            resolved_text = re.sub(r'\s+([?.!,"])', r'\1', resolved_text)
            return resolved_text.strip()
        except Exception as e:
            # Log and handle any errors, returning the original text as a fallback
            print(f"Coreference resolution error: {e}")
            return text

    def srl(self, sentence):
        """
        Performs SRL (Semantic Role Labeling) on the input sentence and converts active to passive.
        """
        passive_sentence = active_to_passive(sentence)
        return passive_sentence

    # def srl(self, sentence):
    #     """
    #     Converts active sentences to passive for questions and retains non-questions as is.

    #     Args:
    #         sentence (str): Input sentence.

    #     Returns:
    #         str: Converted sentence in passive voice (if a question) or unchanged.
    #     """
    #     # Check if the sentence ends with a question mark
    #     if sentence.strip().endswith('?'):
    #         # Convert the active voice question to passive
    #         passive_sentence = active_to_passive(sentence)
    #         if not passive_sentence.strip().endswith('?'):
    #             # Ensure the passive sentence still ends with a question mark
    #             passive_sentence = passive_sentence.strip() + '?'
    #         return passive_sentence
        # else:
        #     # Return the sentence unchanged if it's not a question
        #     return sentence

    def logic(self, sentence):
        """
        Transforms a sentence with an 'if...then...' structure by swapping the condition and conclusion.

        Args:
            sentence (str): Input sentence with 'if...then...' structure.

        Returns:
            str: Transformed sentence with swapped condition and conclusion.
        """
        # Check if the sentence contains "if...then..."
        match = re.search(r'if (.*), then (.*)', sentence, re.IGNORECASE)
        if match:
            condition = match.group(1).strip().rstrip('.')
            conclusion = match.group(2).strip().rstrip('.')

            # Swap the condition and conclusion
            transformed_sentence = f"If {conclusion}, then {condition}"
            return transformed_sentence

        # If no 'if...then...' is found, return the original sentence with a note
        return "No 'if...then...' structure found in the sentence."

    # def fairness(self, sentence):
    #     """
    #     Adds gender-specific words ('female' or 'male') to a sentence if no gender word is present.

    #     Args:
    #         sentence (str): Input sentence.

    #     Returns:
    #         str: Sentence with randomly added gender word if none is present.
    #     """
    #     # Define gender-specific words to check
    #     gender_words = {"female", "male", "woman", "man", "girl", "boy", "she", "he", "her", "his"}
    #     tokens = word_tokenize(sentence.lower())

    #     # Check if the sentence already contains a gender word
    #     if any(word in tokens for word in gender_words):
    #         return sentence  # Return original sentence if gender word exists

    #     # Randomly select 'female' or 'male'
    #     gender_word = random.choice(["female", "male"])

    #     # Tokenize and tag parts of speech
    #     tagged = pos_tag(word_tokenize(sentence))

    #     # Identify where to insert the gender word
    #     new_tokens = []
    #     inserted = False
    #     for word, tag in tagged:
    #         # Insert gender word before a noun (NN, NNP, etc.)
    #         if not inserted and tag in {"NN", "NNP", "NNS", "NNPS"}:
    #             new_tokens.append(gender_word)
    #             inserted = True
    #         new_tokens.append(word)

    #     # If no noun is found, append the gender word to the start
    #     if not inserted:
    #         new_tokens.insert(0, gender_word)

    #     # Join tokens and return the updated sentence
    #     updated_sentence = " ".join(new_tokens)
    #     updated_sentence = re.sub(r'\s+([?.!,"])', r'\1', updated_sentence)  # Fix spaces before punctuation
    #     return updated_sentence

    def fairness(self, sentence):
        """
        Adds gender-specific words ('female' or 'male') to a sentence if no gender word is present.
        If the main noun is not human, adds nationality-specific words ('American', 'Japanese', 'Korean', etc.) instead.

        Args:
            sentence (str): Input sentence.

        Returns:
            str: Sentence with added gender or nationality word if none is present.
        """
        # Define gender-specific and nationality-specific words
        gender_words = {"female", "male", "woman", "man",
                        "girl", "boy", "she", "he", "her", "his"}
        nationality_words = ["American", "Japanese", "Korean",
                             "Indian", "Canadian", "Brazilian", "German"]

        # Tokenize and tag parts of speech
        tokens = word_tokenize(sentence)
        tagged = pos_tag(tokens)

        # Check if the sentence already contains a gender word
        if any(word.lower() in gender_words for word in tokens):
            return sentence  # Return original sentence if gender word exists

        # Identify the main noun and check if it is human
        main_noun = None
        for word, tag in tagged:
            if tag in {"NN", "NNS", "NNP", "NNPS"}:  # Nouns
                main_noun = word
                break

        # Check if the main noun is human using WordNet
        if main_noun:
            synsets = wn.synsets(main_noun, pos=wn.NOUN)
            if synsets:
                for synset in synsets:
                    if "person" in synset.lexname():
                        # Main noun is human, add a gender word
                        gender_word = random.choice(
                            ["female", "male", "American", "Japanese"])
                        tokens.insert(tokens.index(main_noun), gender_word)
                        # Ensure no space before punctuation
                        return re.sub(r'\s+([?.!,"])', r'\1', " ".join(tokens))

            # Main noun is not human, add a nationality word
            nationality_word = random.choice(nationality_words)
            tokens.insert(tokens.index(main_noun), nationality_word)
            # Ensure no space before punctuation
            return re.sub(r'\s+([?.!,"])', r'\1', " ".join(tokens))

        # If no main noun is found, prepend a nationality word
        nationality_word = random.choice(nationality_words)
        # Ensure no space before punctuation
        return re.sub(r'\s+([?.!,"])', r'\1', f"{nationality_word} {sentence}")

    def correct_grammar(self, text):
        """
        Corrects grammar using LanguageTool's public API.

        Args:
            text (str): Input text.

        Returns:
            str: Text with corrected grammar.
        """
        url = "https://api.languagetool.org/v2/check"
        params = {
            'text': text,
            'language': 'en-US'
        }
        response = requests.post(url, data=params)
        if response.status_code == 200:
            matches = response.json().get('matches', [])
            for match in matches:
                replacements = match.get('replacements', [])
                if replacements:
                    replacement = replacements[0].get('value', '')
                    start = match['offset']
                    end = start + match['length']
                    text = text[:start] + replacement + text[end:]
            return text
        else:
            return text  # Return original text if API fails

    def temporal(self, sentence):
        """
        Transforms present tense sentences into temporal context by adding past statements
        with opposite sentiment. Ensures the sentence is lowercased and contextual.

        Args:
            sentence (str): Input sentence.

        Returns:
            str: Temporally transformed sentence.
        """
        def get_antonym(word):
            """Retrieve an antonym for the given word."""
            antonyms = set()
            for synset in wn.synsets(word):
                for lemma in synset.lemmas():
                    if lemma.antonyms():
                        antonyms.add(lemma.antonyms()[0].name())
            return random.choice(list(antonyms)) if antonyms else None

        def find_subject(sentence):
            """Find the main subject (noun/proper noun) of the sentence."""
            doc = self.nlp(sentence)
            for token in doc:
                if token.dep_ in {"nsubj", "pobj", "dobj"} and token.pos_ in {"NOUN", "PROPN"}:
                    return token.text
            return "it"  # Fallback if no subject is found

        # Lowercase the sentence
        sentence = sentence.lower()

        # Detect tense and sentiment-related words
        doc = self.nlp(sentence)
        tense = None
        sentiment_word = None
        for token in doc:
            if token.tag_ in {'VBP', 'VBZ'}:  # Present tense verbs
                tense = 'present'
            # Find sentiment words (adjective/adverb)
            if token.pos_ in {"ADJ", "ADV"}:
                sentiment_word = token.text

        # If sentence is not present tense, return as is
        if tense != 'present':
            return sentence.capitalize()

        # Find antonym for the sentiment word
        antonym = get_antonym(sentiment_word) if sentiment_word else None
        subject = find_subject(sentence)

        # Construct the transformed sentence

        past_phrase = f"{subject} was not like this"
        # past_phrase = f"{subject} used to be {antonym}" if antonym else f"{subject} was not {sentiment_word}"
        # else:

        transformed_sentence = f"{past_phrase}, but now {sentence}"
        return transformed_sentence.capitalize()

    def ner(self, sentence):
        """
        Replaces location names (GPE entities) in the input sentence with another location name.

        Args:
            sentence (str): Input sentence.

        Returns:
            str: Sentence with location names replaced.
        """
        # List of alternative locations
        location_names = ["Canada", "Australia", "Germany",
                          "France", "India", "Japan", "Brazil"]

        # Parse the sentence using SpaCy
        doc = nlp(sentence)

        # Reconstruct the sentence with replaced locations
        transformed_tokens = []
        for token in doc:
            if token.ent_type_ == "GPE":  # Check if the token is a location
                new_location = random.choice(location_names)
                transformed_tokens.append(new_location)
            else:
                transformed_tokens.append(token.text)

        # Join tokens and fix spaces before punctuation
        transformed_sentence = " ".join(transformed_tokens)
        # Fix spaces before punctuation
        transformed_sentence = re.sub(
            r'\s+([?.!,"])', r'\1', transformed_sentence)
        return transformed_sentence

    def get_random_adjective_or_adverb(self):
        adjectives = set()
        adverbs = set()

        for synset in wordnet.all_synsets(pos=wordnet.ADJ):
            for lemma in synset.lemmas():
                adjectives.add(lemma.name())

        for synset in wordnet.all_synsets(pos=wordnet.ADV):
            for lemma in synset.lemmas():
                adverbs.add(lemma.name())

        if adjectives and random.choice([True, False]):
            word = random.choice(list(adjectives))
            pos_tag = 'JJ'
        elif adverbs:
            word = random.choice(list(adverbs))
            pos_tag = 'RB'
        else:
            return "", ""  # Return empty strings if no words are available

        return word, pos_tag

    def vocab(self, sentence):
        tokens = word_tokenize(sentence)
        word, pos_tag = self.get_random_adjective_or_adverb()

        if not word:
            return sentence  # Return original sentence if no word was found

        if pos_tag == 'JJ':
            tagged = nltk.pos_tag(tokens)
            for i, (token, tag) in enumerate(tagged):
                if tag in ['NN', 'NNS', 'NNP', 'NNPS']:
                    tokens.insert(i, word)
                    break
        elif pos_tag == 'RB':
            tagged = nltk.pos_tag(tokens)
            for i, (token, tag) in enumerate(tagged):
                if tag in ['VB', 'VBD', 'VBG', 'VBN', 'VBP', 'VBZ']:
                    tokens.insert(i + 1, word)
                    break

        new_sentence = ' '.join(tokens)
        return new_sentence
