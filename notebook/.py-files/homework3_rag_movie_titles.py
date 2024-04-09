# -*- coding: utf-8 -*-
"""Homework3-rag-movie-titles.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/13zRMjjM4JjrRFALU8T5ruC9mIuI-Ra2v

# Getting Started with RAG using Fireworks Fast Inference LLMs

<a href="https://colab.research.google.com/github/fw-ai/cookbook/blob/main/recipes/rag/rag-paper-titles.ipynb" target="_parent"><img src="https://colab.research.google.com/assets/colab-badge.svg" alt="Open In Colab"/></a>

While large language models (LLMs) show powerful capabilities that power advanced use cases, they suffer from issues such as factual inconsistency and hallucination. Retrieval-augmented generation (RAG) is a powerful approach to enrich LLM capabilities and improve their reliability. RAG involves combining LLMs with external knowledge by enriching the prompt context with relevant information that helps accomplish a task.

This tutorial shows how to getting started with RAG by leveraging vector store and open-source LLMs. To showcase the power of RAG, this use case will cover building a RAG system that suggests short and easy to read ML paper titles from original ML paper titles. Paper tiles can be too technical for a general audience so using RAG to generate short titles based on previously created short titles can make research paper titles more accessible and used for science communication such as in the form of newsletters or blogs.

Before getting started, let's first install the libraries we will use:
"""

# Commented out IPython magic to ensure Python compatibility.
# %%capture
# !pip install chromadb tqdm fireworks-ai python-dotenv pandas
# !pip install sentence-transformers

!pip install colab-env -qU

!pip install datasets

"""Let's download the dataset we will use:"""

#!wget https://raw.githubusercontent.com/dair-ai/ML-Papers-of-the-Week/main/research/ml-potw-10232023.csv
#!mkdir data
#!mv ml-potw-10232023.csv data/

"""Before continuing, you need to obtain a Fireworks API Key to use the Mistral 7B model.

Checkout this quick guide to obtain your Fireworks API Key: https://readme.fireworks.ai/docs
"""

import fireworks.client
import os
import dotenv
import chromadb
import json
from tqdm.auto import tqdm
import pandas as pd
import random
from google.colab import userdata
from colab_env import envvar_handler

"""**Make sure you have a fireworks api key**"""

import fireworks.client

# Set your FireWorks API key
fireworks.client.api_key = "XXXXXXXXXXXXXXXXXXXXXXXXXX"

"""## Getting Started

Let's define a function to get completions from the Fireworks inference platform.
"""

def get_completion(prompt, model=None, max_tokens=50):

    fw_model_dir = "accounts/fireworks/models/"

    if model is None:
        model = fw_model_dir + "llama-v2-7b"
    else:
        model = fw_model_dir + model

    completion = fireworks.client.Completion.create(
        model=model,
        prompt=prompt,
        max_tokens=max_tokens,
        temperature=0
    )

    return completion.choices[0].text

"""Let's first try the function with a simple prompt:"""

get_completion("Hello, my name is")

"""Now let's test with Mistral-7B-Instruct:"""

mistral_llm = "mistral-7b-instruct-4k"

get_completion("Hello, my name is", model=mistral_llm)

"""The Mistral 7B Instruct model needs to be instructed using special instruction tokens `[INST] <instruction> [/INST]` to get the right behavior. You can find more instructions on how to prompt Mistral 7B Instruct here: https://docs.mistral.ai/llm/mistral-instruct-v0.1"""

mistral_llm = "mistral-7b-instruct-4k"

get_completion("Tell me 2 jokes", model=mistral_llm)

mistral_llm = "mistral-7b-instruct-4k"

get_completion("[INST]Tell me 2 jokes[/INST]", model=mistral_llm)

"""Now let's try with a more complex prompt that involves instructions:"""

prompt = """[INST]
Given the following wedding guest data, write a very short 3-sentences thank you letter:

{
  "name": "John Doe",
  "relationship": "Bride's cousin",
  "hometown": "New York, NY",
  "fun_fact": "Climbed Mount Everest in 2020",
  "attending_with": "Sophia Smith",
  "bride_groom_name": "Tom and Mary"
}

Use only the data provided in the JSON object above.

The senders of the letter is the bride and groom, Tom and Mary.
[/INST]"""

get_completion(prompt, model=mistral_llm, max_tokens=150)

"""## RAG Use Case: Generating Short Paper Titles


The user will provide an original movie title. We will then take that input and then use the dataset to generate a context similar to their search

### Step 1: Load the Dataset

Let's first load the dataset we will use:
"""

from datasets import load_dataset
import pandas as pd
from chromadb import Documents, EmbeddingFunction, Embeddings
from sentence_transformers import SentenceTransformer
from chromadb import Documents, EmbeddingFunction, Embeddings
from sentence_transformers import SentenceTransformer
import random
from tqdm.auto import tqdm
import uuid

# Load movie dataset
ds = load_dataset("Coder-Dragon/wikipedia-movies", split='train[:1000]')

# Convert movie dataset to pandas dataframe
movie_df = pd.DataFrame(ds)

# Extracting only the Title column and Plot
movie_df = movie_df[["Title", "Plot"]]
print(len(movie_df))

movie_df.head()

movie_df.tail()

"""We will be using SentenceTransformer for generating embeddings that we will store to a chroma document store."""

embedding_model = SentenceTransformer('all-MiniLM-L6-v2')

# Define embedding function
class MyEmbeddingFunction(EmbeddingFunction):
    def __call__(self, input: Documents) -> Embeddings:
        batch_embeddings = embedding_model.encode(input)
        return batch_embeddings.tolist()

# Instantiate embedding function
embed_fn = MyEmbeddingFunction()

# Initialize the chromadb directory, and client
client = chromadb.PersistentClient(path="./chromadb")

# Create collection
collection = client.get_or_create_collection(
    name="movies-collection",
    embedding_function=embed_fn
)

"""We will now generate embeddings for batches:"""

batch_size = 50

for i in tqdm(range(0, len(movie_df), batch_size)):
    batch = movie_df.iloc[i:i+batch_size].copy()  # Make a copy to avoid SettingWithCopyWarning

    # Replace empty strings with placeholders
    batch["Title"].fillna("No Title", inplace=True)
    batch["Plot"].fillna("No Plot", inplace=True)

    # Generate embeddings for titles and plots
    batch_embeddings = embedding_model.encode(batch["Title"].tolist() + batch["Plot"].tolist())

    # Split embeddings into title and plot embeddings
    title_embeddings = batch_embeddings[:len(batch)]
    plot_embeddings = batch_embeddings[len(batch):]

    # Generate unique IDs for titles and plots
    title_ids = [str(uuid.uuid4()) for _ in range(len(batch["Title"]))]
    plot_ids = [str(uuid.uuid4()) for _ in range(len(batch["Plot"]))]

    print(f'Batch {i//batch_size + 1}:')
    print(f'Batch size: {batch_size}, Titles: {len(batch["Title"])}, Plots: {len(batch["Plot"])}, Title IDs: {len(title_ids)}, Plot IDs: {len(plot_ids)}, Embeddings length: {len(batch_embeddings)}')

    # Upsert titles and embeddings to ChromaDB
    collection.upsert(
        ids=title_ids,
        documents=batch["Title"].tolist(),
        embeddings=title_embeddings
    )

    # Upsert plots and embeddings to ChromaDB
    collection.upsert(
        ids=plot_ids,
        documents=batch["Plot"].tolist(),
        embeddings=plot_embeddings
    )

"""Now we can test the retriever:"""

collection = client.get_or_create_collection(
    name="movies-collection",
    embedding_function=embed_fn
)

# Example query for movie titles
query_text = ["action movie"]

# Query the collection for similar movie titles
retriever_results = collection.query(
    query_texts=query_text,
    n_results=2,
)

# Print the retrieved movie titles
print(retriever_results["documents"])

"""Now let's put together our final prompt:"""

def search_and_generate_suggested_titles(user_query):
    # Query for user query
    results = collection.query(
        query_texts=[user_query],
        n_results=10,
    )

    # Extract retrieved movie titles
    retrieved_titles = results

    # Concatenate titles into a single string
    retrieved_titles_str = '\n'.join(retrieved_titles)

    # Prompt template for suggesting movie titles
    prompt_template = f'''[INST]

        Your main task is to generate 5 SUGGESTED_TITLES based on the MOVIE_TITLE and PLOT.

        You should mimic a similar style and length as the retrieved titles but PLEASE DO NOT include them in the SUGGESTED_TITLES, only generate versions of the MOVIE_TITLE.

        MOVIE_TITLE and PLOT: {user_query}

        SUGGESTED_TITLES:

        [/INST]
        '''

    # Get model suggestions based on the prompt
    responses = get_completion(prompt_template, model=mistral_llm, max_tokens=2000)
    suggested_titles = ''.join([str(r) for r in responses])

    # Print the suggestions
    print("Model Suggestions:")
    print(suggested_titles)
    print("\n\n\nPrompt Template:")
    print(prompt_template)

# Example usage
search_and_generate_suggested_titles("Documentaries showcasing indigenous peoples' survival and daily life in Arctic regions")

search_and_generate_suggested_titles("Western romance")

search_and_generate_suggested_titles("Silent film about a Parisian star moving to Egypt, leaving her husband for a baron, and later reconciling after finding her family in poverty in Cairo.")

search_and_generate_suggested_titles("Comedy film, office disguises, boss's daughter, elopement.")

search_and_generate_suggested_titles("Lost film, Cleopatra charms Caesar, plots world rule, treasures from mummy, revels with Antony, tragic end with serpent in Alexandria.")

search_and_generate_suggested_titles("Denis Gage Deane-Tanner")

"""As you can see, the short titles generated by the LLM are somewhat okay. This use case still needs a lot more work and could potentially benefit from finetuning as well. For the purpose of this tutorial, we have provided a simple application of RAG using open-source models from Firework's blazing-fast models.

Try out other open-source models here: https://app.fireworks.ai/models

Read more about the Fireworks APIs here: https://readme.fireworks.ai/reference/createchatcompletion

"""