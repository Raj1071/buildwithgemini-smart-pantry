# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import base64
import datetime
import json
import os
import re
import subprocess
import urllib.parse
import urllib.request
import uuid
from zoneinfo import ZoneInfo
from google import genai
from google.cloud import firestore, storage
from google.oauth2.credentials import Credentials

from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.schema.manager import A2uiSchemaManager

from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.code_executors import AgentEngineSandboxCodeExecutor
from google.adk.memory import VertexAiMemoryBankService
from google.adk.models import Gemini
from google.adk.tools import ToolContext
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.genai import types

try:
    from .a2ui_utils import a2ui_callback
except ImportError:
    from a2ui_utils import a2ui_callback

# Hardcoded project ID as required (must be project ID, not project number)
FIRESTORE_PROJECT_ID = "qwiklabs-gcp-01-8d42beb94564"

# Hardcoded Cloud Storage bucket name
GCS_BUCKET_NAME = "smart-pantry-media-8d42beb94564"

# Deployed Memory Bank Instance ID
MEMORY_BANK_ID = "8539517585819959296"


def _get_firestore_client() -> firestore.Client:
    """Helper to initialize the Firestore client for project ID with fallback for local dev."""
    try:
        token = (
            subprocess.check_output(["gcloud", "auth", "print-access-token"])
            .decode()
            .strip()
        )
        creds = Credentials(token)
        return firestore.Client(project=FIRESTORE_PROJECT_ID, credentials=creds)
    except Exception:
        return firestore.Client(project=FIRESTORE_PROJECT_ID)


def _get_agent_engine_resource_name() -> str | None:
    """Reads Agent Engine resource name from deployment_metadata.json if available."""
    try:
        metadata_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "deployment_metadata.json",
        )
        if os.path.exists(metadata_path):
            with open(metadata_path, "r") as f:
                data = json.load(f)
                return data.get("remote_agent_runtime_id")
    except Exception:
        pass
    return "projects/82502274399/locations/us-east1/reasoningEngines/8539517585819959296"


async def generate_memories_callback(callback_context: CallbackContext):
    """WRITE: After each turn, send the session to Memory Bank for extraction."""
    try:
        await callback_context.add_session_to_memory()
    except Exception as e:
        print(f"Memory extraction skipped: {e}")
    return None


def memory_bank_service_builder():
    """Builds VertexAiMemoryBankService pointing to the deployed Agent Engine Memory Bank."""
    return VertexAiMemoryBankService(
        project=FIRESTORE_PROJECT_ID,
        location="us-east1",
        agent_engine_id=MEMORY_BANK_ID,
    )


def get_pantry_items(category: str = "") -> str:
    """Gets items from the pantry collection in Firestore.

    Args:
        category: Optional category filter (e.g. 'Produce', 'Pantry').

    Returns:
        A list of pantry items in the database.
    """
    db = _get_firestore_client()
    query_ref = db.collection("pantry")
    if category:
        query_ref = query_ref.where("category", "==", category)

    docs = query_ref.stream()
    items = [doc.to_dict() for doc in docs]
    if not items:
        return "No pantry items found."
    return f"Pantry items: {items}"


def add_pantry_item(
    name: str, quantity: str, category: str = "Pantry", expiry: str = ""
) -> str:
    """Adds a new item to the pantry collection in Firestore.

    Args:
        name: Name of the pantry item (e.g. 'Eggs', 'Milk').
        quantity: Quantity of the item (e.g. '1 dozen', '1 liter').
        category: Category of the item (default: 'Pantry').
        expiry: Optional expiration date string.

    Returns:
        Confirmation message.
    """
    db = _get_firestore_client()
    doc_id = f"pantry_{name.lower().replace(' ', '_')}"
    item_data = {
        "id": doc_id,
        "name": name,
        "quantity": quantity,
        "category": category,
        "expiry": expiry,
    }
    db.collection("pantry").document(doc_id).set(item_data)
    return f"Successfully added {name} ({quantity}) to pantry."


def search_recipes(ingredient: str = "") -> str:
    """Searches recipes in the recipes collection in Firestore.

    Args:
        ingredient: Optional ingredient filter (e.g. 'Tomatoes', 'Garlic').

    Returns:
        Matching recipes from the database.
    """
    db = _get_firestore_client()
    docs = db.collection("recipes").stream()
    recipes = [doc.to_dict() for doc in docs]

    if ingredient:
        matching = [
            r
            for r in recipes
            if any(
                ingredient.lower() in ing.lower()
                for ing in r.get("ingredients", [])
            )
        ]
        if not matching:
            return f"No recipes found containing ingredient '{ingredient}'."
        return f"Recipes matching '{ingredient}': {matching}"

    return f"All recipes: {recipes}"


def fetch_online_recipes(query: str) -> str:
    """Fetches real online recipes and meal ideas from the public TheMealDB API.

    Args:
        query: Dish or ingredient query string (e.g. 'pasta', 'chicken', 'salad').

    Returns:
        A list of matching recipe details including title, area/cuisine, ingredients, instructions, and thumbnail image.
    """
    api_key = os.getenv("THEMEALDB_API_KEY", "1")
    encoded_query = urllib.parse.quote(query.strip())
    url = f"https://www.themealdb.com/api/json/v1/{api_key}/search.php?s={encoded_query}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SmartPantry/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())

        meals = data.get("meals")
        if not meals:
            return f"No online recipes found for '{query}'."

        results = []
        for m in meals[:3]:
            ingredients = []
            for i in range(1, 21):
                ing = m.get(f"strIngredient{i}")
                meas = m.get(f"strMeasure{i}")
                if ing and ing.strip():
                    item = ing.strip()
                    if meas and meas.strip():
                        item += f" ({meas.strip()})"
                    ingredients.append(item)

            results.append(
                {
                    "title": m.get("strMeal"),
                    "category": m.get("strCategory"),
                    "area": m.get("strArea"),
                    "image": m.get("strMealThumb"),
                    "ingredients": ingredients,
                    "instructions": (m.get("strInstructions") or "")[:200]
                    + "...",
                }
            )

        return f"Online recipes for '{query}': {results}"
    except Exception as e:
        return f"Error fetching online recipes: {e}"


def search_grocery_products(query: str) -> str:
    """Searches real grocery products, brand info, and Nutri-Score from Open Food Facts API.

    Args:
        query: Grocery or food product search term (e.g. 'organic pasta', 'olive oil').

    Returns:
        Product details including product name, brand, Nutri-Score grade, categories, and image URL.
    """
    user_agent = os.getenv(
        "OPENFOODFACTS_USER_AGENT", "SmartPantryApp/1.0 (contact@smartpantry.app)"
    )
    encoded_query = urllib.parse.quote(query.strip())
    url = f"https://world.openfoodfacts.org/cgi/search.pl?search_terms={encoded_query}&search_simple=1&action=process&json=1"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": user_agent})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())

        products = data.get("products", [])
        if not products:
            return f"No grocery products found for '{query}'."

        results = []
        for p in products[:3]:
            results.append(
                {
                    "product_name": p.get("product_name")
                    or p.get("product_name_en")
                    or "Unknown Product",
                    "brands": p.get("brands", "Unknown Brand"),
                    "nutriscore": p.get("nutriscore_grade", "N/A").upper(),
                    "categories": p.get("categories", "Uncategorized"),
                    "image_url": p.get("image_front_small_url")
                    or p.get("image_url"),
                }
            )

        return f"Grocery products for '{query}': {results}"
    except Exception as e:
        return f"Error fetching grocery product info: {e}"


def add_recipe(
    title: str, ingredients: list[str], instructions: str, prep_time: str = "15 mins"
) -> str:
    """Adds a new recipe to the recipes collection in Firestore.

    Args:
        title: Title of the recipe.
        ingredients: List of ingredients required.
        instructions: Cooking instructions.
        prep_time: Preparation time string.

    Returns:
        Confirmation message.
    """
    db = _get_firestore_client()
    doc_id = f"recipe_{title.lower().replace(' ', '_')}"
    recipe_data = {
        "id": doc_id,
        "title": title,
        "ingredients": ingredients,
        "instructions": instructions,
        "prep_time": prep_time,
    }
    db.collection("recipes").document(doc_id).set(recipe_data)
    return f"Successfully added recipe '{title}'."


async def generate_item_image(prompt: str, tool_context: ToolContext) -> str:
    """Generates an image for a food item or recipe using gemini-3.1-flash-lite-image in global region.

    Args:
        prompt: Description of the food dish or pantry item to generate an image for.

    Returns:
        Public HTTP URL of the uploaded image in Cloud Storage.
    """
    client = genai.Client(
        vertexai=True, project=FIRESTORE_PROJECT_ID, location="global"
    )

    response = client.models.generate_content(
        model="gemini-3.1-flash-lite-image", contents=prompt
    )

    image_bytes = None
    mime_type = "image/jpeg"

    if (
        response.candidates
        and response.candidates[0].content
        and response.candidates[0].content.parts
    ):
        for part in response.candidates[0].content.parts:
            if part.inline_data:
                image_bytes = part.inline_data.data
                mime_type = part.inline_data.mime_type or "image/jpeg"
                break

    if not image_bytes:
        return "Error: No image bytes returned from gemini-3.1-flash-lite-image model."

    slug = re.sub(r"[^a-z0-9]", "_", prompt.lower()).strip("_")[:30]
    filename = f"dish_{slug}_{uuid.uuid4().hex[:6]}.jpg"

    # 1. Save artifact to tool_context so it shows up in Playground's Artifacts panel
    artifact_part = types.Part(
        inline_data=types.Blob(mime_type=mime_type, data=image_bytes)
    )

    try:
        await tool_context.save_artifact(filename, artifact_part)
    except Exception:
        pass

    # 2. Upload image bytes directly to GCS bucket without writing to a local file
    try:
        storage_client = storage.Client(project=FIRESTORE_PROJECT_ID)
        bucket = storage_client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(filename)
        blob.upload_from_string(image_bytes, content_type=mime_type)
        return f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{filename}"
    except Exception as e:
        return f"Error uploading image to Cloud Storage: {e}"


async def generate_item_video(prompt: str, tool_context: ToolContext) -> str:
    """Generates a short video for a food item or recipe scene using gemini-omni-flash-preview in global region.

    Args:
        prompt: Description of the food dish, recipe, or cooking scene to generate a video for.

    Returns:
        Public HTTP URL of the uploaded video in Cloud Storage.
    """
    client = genai.Client(
        vertexai=True, project=FIRESTORE_PROJECT_ID, location="global"
    )

    try:
        interaction = client.interactions.create(
            model="gemini-omni-flash-preview", input=prompt
        )
    except Exception as e:
        return f"Error generating video with gemini-omni-flash-preview: {e}"

    if (
        not hasattr(interaction, "output_video")
        or not interaction.output_video
        or not interaction.output_video.data
    ):
        return "Error: No video data returned from gemini-omni-flash-preview model."

    raw_data = interaction.output_video.data
    mime_type = getattr(interaction.output_video, "mime_type", None) or "video/mp4"

    if isinstance(raw_data, str):
        video_bytes = base64.b64decode(raw_data)
    else:
        video_bytes = raw_data

    slug = re.sub(r"[^a-z0-9]", "_", prompt.lower()).strip("_")[:30]
    filename = f"video_{slug}_{uuid.uuid4().hex[:6]}.mp4"

    # 1. Save artifact to tool_context so it shows up in Playground's Artifacts panel
    artifact_part = types.Part(
        inline_data=types.Blob(mime_type=mime_type, data=video_bytes)
    )

    try:
        await tool_context.save_artifact(filename, artifact_part)
    except Exception:
        pass

    # 2. Upload video bytes directly to GCS bucket without writing to a local file
    try:
        storage_client = storage.Client(project=FIRESTORE_PROJECT_ID)
        bucket = storage_client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(filename)
        blob.upload_from_string(video_bytes, content_type=mime_type)
        return f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{filename}"
    except Exception as e:
        return f"Error uploading video to Cloud Storage: {e}"


def get_weather(query: str) -> str:
    """Simulates a web search for weather information.

    Args:
        query: Location query string.
    """
    if "sf" in query.lower() or "san francisco" in query.lower():
        return "It's 60 degrees and foggy."
    return "It's 90 degrees and sunny."


def get_current_time(query: str) -> str:
    """Simulates getting current time for a city.

    Args:
        query: City name query string.
    """
    if "sf" in query.lower() or "san francisco" in query.lower():
        tz_identifier = "America/Los_Angeles"
    else:
        return f"Sorry, I don't have timezone information for query: {query}."

    tz = ZoneInfo(tz_identifier)
    now = datetime.datetime.now(tz)
    return f"The current time for query {query} is {now.strftime('%Y-%m-%d %H:%M:%S %Z%z')}"


agent_engine_id = _get_agent_engine_resource_name()

# Configure A2UI Schema Manager with Basic Catalog v0.8
a2ui_schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

a2ui_instruction = a2ui_schema_manager.generate_system_prompt(
    role_description="You are Smart Pantry, a helpful AI cooking and pantry management assistant.",
    workflow_description="Analyze the request and return structured UI when appropriate.",
    ui_description=(
        "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows. "
        "Never nest a Card inside a Card. "
        "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
        "Table or Heading (unsupported), or Buttons, actions, or forms (they do "
        "nothing in adk web). "
        "You may include one Image component, but only when you have a public https "
        "URL for the image (for example the URL an image tool returns after uploading "
        "to a public bucket). Set the Image url to that exact https link, for example "
        '{"Image": {"url": {"literalString": "https://..."}}}. Never point an '
        "Image at a bare filename, an artifact name, or a non-http(s) path. If you do "
        "not have a public URL, add a short Text line noting the image instead. "
        "No markdown in text; use the usageHint property ('h1', 'h2', 'body') for "
        "headings and emphasis. "
        "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in "
        "<a2a_datapart_json> tags or 'kind'/'data'/'metadata' objects. "
        "Always pay close attention to, remember, and respect all user allergies (e.g., nuts, gluten, dairy, shellfish, etc.), dietary preferences, and restrictions across sessions. "
        "When suggesting recipes, checking pantry items, or planning meals, ensure that items containing known user allergens are explicitly avoided or flagged. "
        "Use your Firestore tools to read and update pantry items and local recipes for users, "
        "use fetch_online_recipes to search live web recipes from TheMealDB API, "
        "use search_grocery_products to look up branded grocery items and Nutri-Scores from Open Food Facts, "
        "use generate_item_image to create real AI images of food items and dishes using gemini-3.1-flash-lite-image, "
        "use generate_item_video to create AI video clips of food preparation or dishes using gemini-omni-flash-preview, "
        "and use code execution to safely run Python scripts in an Agent Engine sandbox when calculations or code analysis are needed."
    ),
    include_schema=True,
    include_examples=True,
)

root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model="gemini-flash-latest",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    code_executor=AgentEngineSandboxCodeExecutor(
        agent_engine_resource_name=agent_engine_id
    )
    if agent_engine_id
    else None,
    after_agent_callback=generate_memories_callback,
    after_model_callback=a2ui_callback,
    instruction=a2ui_instruction,
    tools=[
        PreloadMemoryTool(),
        get_pantry_items,
        add_pantry_item,
        search_recipes,
        fetch_online_recipes,
        search_grocery_products,
        add_recipe,
        generate_item_image,
        generate_item_video,
        get_weather,
        get_current_time,
    ],
)

app = App(
    root_agent=root_agent,
    name="app",
)
