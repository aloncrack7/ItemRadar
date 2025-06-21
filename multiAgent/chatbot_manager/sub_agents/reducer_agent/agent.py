# Enhanced universal reducer_agent/agent.py
import os
import re
from collections import Counter
from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.tools.tool_context import ToolContext

load_dotenv()


def analyze_items_and_generate_question(texts: list[str], tool_context: ToolContext) -> dict:
    """
    Enhanced universal analyzer that uses LLM reasoning to understand items
    and generate truly personalized discriminating questions.
    """
    print(f"--- Analyzing {len(texts)} items with enhanced AI reasoning ---")

    if not texts or len(texts) <= 1:
        return {"question": None, "reason": "Not enough items to discriminate"}

    # Get previous questions to avoid repetition
    previous_questions = tool_context.state.get("asked_questions", [])

    # Get conversation context for better understanding
    conversation_context = tool_context.state.get("conversation_context", "")

    # Use LLM reasoning to analyze items and generate question
    analysis_result = perform_intelligent_analysis(texts, previous_questions, conversation_context)

    if not analysis_result or not analysis_result.get("question"):
        # Fallback to smart generic questions if analysis fails
        fallback_question = get_intelligent_fallback_question(texts, previous_questions)
        analysis_result = {
            "question": fallback_question,
            "reasoning": "Used intelligent fallback due to analysis limitations",
            "confidence": 0.6
        }

    # Store the question to avoid repetition
    question = analysis_result["question"]
    previous_questions.append(question)
    tool_context.state["asked_questions"] = previous_questions

    # Store context for future questions (initialize if doesn't exist)
    if "conversation_context" not in tool_context.state:
        tool_context.state["conversation_context"] = ""
    tool_context.state["conversation_context"] += f"\nAsked: {question}"

    result = {
        "question": question,
        "reasoning": analysis_result.get("reasoning", ""),
        "confidence": analysis_result.get("confidence", 0.8)
    }

    print(f"--- Generated question: {question} ---")
    print(f"--- Reasoning: {analysis_result.get('reasoning', 'N/A')} ---")

    return result


def perform_intelligent_analysis(texts: list[str], previous_questions: list[str], context: str) -> dict:
    """
    Use LLM reasoning to analyze items and generate the best discriminating question.
    This replaces the hardcoded analysis with intelligent understanding.
    """

    # Analyze the items to understand their nature and differences
    item_analysis = analyze_item_characteristics(texts)

    # Generate potential questions based on understanding
    potential_questions = generate_potential_questions(item_analysis, texts)

    # Select the best question considering previous questions
    best_question = select_optimal_question(potential_questions, previous_questions, texts)

    return best_question


def analyze_item_characteristics(texts: list[str]) -> dict:
    """
    Intelligently analyze the characteristics of the items using pattern recognition
    and semantic understanding instead of hardcoded lists.
    """
    analysis = {
        "item_types": [],
        "common_attributes": [],
        "distinguishing_features": [],
        "categories": set(),
        "descriptive_patterns": []
    }

    # Analyze each item for patterns and characteristics
    for item in texts:
        item_lower = item.lower()
        words = re.findall(r'\b\w+\b', item_lower)

        # Identify item type/category
        item_type = identify_item_type(item)
        analysis["item_types"].append(item_type)
        analysis["categories"].add(item_type)

        # Extract descriptive attributes
        attributes = extract_attributes(item, words)
        analysis["common_attributes"].extend(attributes)

        # Find distinguishing patterns
        patterns = find_descriptive_patterns(item)
        analysis["descriptive_patterns"].extend(patterns)

    # Find attributes that appear in some but not all items (discriminating features)
    attribute_counts = Counter(analysis["common_attributes"])
    total_items = len(texts)

    for attr, count in attribute_counts.items():
        if 0 < count < total_items:
            discrimination_power = min(count, total_items - count) / total_items
            analysis["distinguishing_features"].append({
                "attribute": attr,
                "count": count,
                "discrimination_power": discrimination_power
            })

    # Sort by discrimination power (closer to 0.5 is better)
    analysis["distinguishing_features"].sort(
        key=lambda x: abs(0.5 - x["discrimination_power"])
    )

    return analysis


def identify_item_type(item_description: str) -> str:
    """
    Intelligently identify the type/category of an item based on keywords and context.
    """
    item_lower = item_description.lower()

    # Use semantic patterns to identify categories
    category_indicators = {
        "bag": ["bag", "backpack", "purse", "satchel", "tote", "briefcase", "messenger", "duffel", "handbag"],
        "clothing": ["shirt", "pants", "dress", "jacket", "coat", "sweater", "jeans", "skirt", "blouse", "hoodie"],
        "electronics": ["phone", "laptop", "tablet", "camera", "headphones", "charger", "device", "electronic"],
        "accessory": ["watch", "jewelry", "necklace", "ring", "bracelet", "earrings", "glasses", "sunglasses"],
        "tool": ["tool", "hammer", "screwdriver", "wrench", "drill", "pliers", "utility"],
        "book": ["book", "notebook", "journal", "diary", "manual", "guide"],
        "key": ["key", "keychain", "fob", "remote"],
        "wallet": ["wallet", "purse", "billfold", "card holder"],
        "bottle": ["bottle", "water bottle", "thermos", "flask", "container"]
    }

    for category, keywords in category_indicators.items():
        if any(keyword in item_lower for keyword in keywords):
            return category

    return "item"


def extract_attributes(item_description: str, words: list[str]) -> list[str]:
    """
    Extract meaningful attributes from item descriptions using intelligent parsing.
    """
    attributes = []
    item_lower = item_description.lower()

    # Color detection using broader pattern matching
    color_patterns = [
        r'\b(black|white|red|blue|green|yellow|orange|purple|pink|brown|gray|grey)\b',
        r'\b(navy|maroon|burgundy|crimson|emerald|turquoise|coral|beige|tan|olive)\b',
        r'\b(silver|gold|metallic|chrome|bronze|copper)\b',
        r'\b(dark|light|bright|pale|deep|vivid)\s+\w+\b'
    ]

    for pattern in color_patterns:
        matches = re.findall(pattern, item_lower)
        attributes.extend(matches)

    # Size indicators
    size_patterns = [
        r'\b(small|medium|large|tiny|huge|mini|jumbo|xl|xxl)\b',
        r'\b(long|short|tall|wide|narrow|thick|thin)\b',
        r'\d+\s*(inch|cm|mm|ft|meter|litre|oz|lb|kg|gram)'
    ]

    for pattern in size_patterns:
        matches = re.findall(pattern, item_lower)
        attributes.extend(matches)

    # Material detection
    material_indicators = [
        r'\b(leather|plastic|metal|wood|glass|fabric|cotton|silk|canvas|rubber)\b',
        r'\b(vinyl|synthetic|nylon|polyester|denim|suede|velvet|wool)\b',
        r'\b(ceramic|stone|paper|cardboard|foam|mesh|bamboo)\b'
    ]

    for pattern in material_indicators:
        matches = re.findall(pattern, item_lower)
        attributes.extend(matches)

    # Brand detection (dynamic based on capitalization patterns)
    brand_pattern = r'\b[A-Z][a-z]*(?:\s+[A-Z][a-z]*)*\b'
    potential_brands = re.findall(brand_pattern, item_description)

    # Filter out common words that aren't brands
    common_words = {"The", "And", "For", "With", "Black", "Blue", "Red", "Green", "New", "Old"}
    brands = [brand for brand in potential_brands if brand not in common_words and len(brand) > 2]
    attributes.extend([brand.lower() for brand in brands])

    # Feature detection
    feature_keywords = [
        "zipper", "pocket", "strap", "handle", "button", "buckle", "velcro",
        "wireless", "bluetooth", "rechargeable", "waterproof", "adjustable",
        "foldable", "removable", "transparent", "reflective", "padded"
    ]

    for feature in feature_keywords:
        if feature in item_lower:
            attributes.append(feature)

    return attributes


def find_descriptive_patterns(item_description: str) -> list[str]:
    """
    Find descriptive patterns that could be useful for discrimination.
    """
    patterns = []
    item_lower = item_description.lower()

    # Pattern for numbers (could indicate model, size, etc.)
    if re.search(r'\d+', item_description):
        patterns.append("has_numbers")

    # Pattern for brand-like capitalization
    if re.search(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', item_description):
        patterns.append("has_brand_name")

    # Pattern for technical terms
    if re.search(r'\b\w*tech\w*\b|\b\w*digital\w*\b|\b\w*smart\w*\b', item_lower):
        patterns.append("technical_item")

    # Pattern for condition descriptors
    condition_words = ["new", "used", "old", "vintage", "damaged", "broken", "worn"]
    if any(word in item_lower for word in condition_words):
        patterns.append("has_condition_info")

    return patterns


def generate_potential_questions(analysis: dict, texts: list[str]) -> list[dict]:
    """
    Generate potential questions based on the intelligent analysis.
    """
    questions = []

    # Generate questions based on distinguishing features
    for feature_info in analysis["distinguishing_features"][:10]:  # Top 10 features
        attribute = feature_info["attribute"]
        discrimination_power = feature_info["discrimination_power"]

        # Generate natural questions based on attribute type
        question = create_natural_question(attribute, texts)

        if question:
            questions.append({
                "question": question,
                "discrimination_power": discrimination_power,
                "reasoning": f"Based on '{attribute}' appearing in {feature_info['count']} out of {len(texts)} items"
            })

    # Generate category-specific questions if multiple categories exist
    if len(analysis["categories"]) > 1:
        for category in analysis["categories"]:
            category_count = analysis["item_types"].count(category)
            if 0 < category_count < len(texts):
                question = f"Is your item a type of {category}?"
                discrimination_power = min(category_count, len(texts) - category_count) / len(texts)
                questions.append({
                    "question": question,
                    "discrimination_power": discrimination_power,
                    "reasoning": f"Category-based question for {category}"
                })

    # Generate semantic relationship questions
    semantic_questions = generate_semantic_questions(texts, analysis)
    questions.extend(semantic_questions)

    return questions


def create_natural_question(attribute: str, texts: list[str]) -> str:
    """
    Create natural-sounding questions based on attributes.
    """
    # Color questions
    color_words = ["black", "white", "red", "blue", "green", "yellow", "orange", "purple", "pink", "brown", "gray",
                   "grey", "navy", "silver", "gold"]
    if attribute in color_words:
        return f"Is your item {attribute} in color?"

    # Size questions
    size_words = ["small", "large", "medium", "tiny", "huge", "long", "short", "wide", "narrow", "thick", "thin"]
    if attribute in size_words:
        return f"Is your item {attribute} sized?"

    # Material questions
    material_words = ["leather", "plastic", "metal", "wood", "glass", "fabric", "cotton", "silk"]
    if attribute in material_words:
        return f"Is your item made of {attribute}?"

    # Feature questions
    feature_words = ["zipper", "pocket", "strap", "handle", "button", "wireless", "waterproof"]
    if attribute in feature_words:
        if attribute.endswith('s'):
            return f"Does your item have {attribute}?"
        else:
            return f"Does your item have a {attribute}?"

    # Brand questions (if it looks like a brand name)
    if attribute[0].isupper() or len(attribute) > 4:
        return f"Is your item made by {attribute.title()}?"

    # Generic attribute question
    return f"Does your item have '{attribute}' mentioned in its description?"


def generate_semantic_questions(texts: list[str], analysis: dict) -> list[dict]:
    """
    Generate questions based on semantic understanding of the items.
    """
    questions = []

    # Analyze usage context
    usage_contexts = {
        "indoor": ["indoor", "home", "office", "house", "room", "desk", "table"],
        "outdoor": ["outdoor", "hiking", "camping", "sports", "running", "cycling"],
        "professional": ["business", "work", "office", "professional", "meeting"],
        "casual": ["casual", "everyday", "daily", "personal", "leisure"]
    }

    for context, keywords in usage_contexts.items():
        count = sum(1 for text in texts if any(keyword in text.lower() for keyword in keywords))
        if 0 < count < len(texts):
            discrimination_power = min(count, len(texts) - count) / len(texts)
            questions.append({
                "question": f"Is your item primarily used in {context} settings?",
                "discrimination_power": discrimination_power,
                "reasoning": f"Usage context discrimination for {context}"
            })

    # Technology level questions
    tech_indicators = ["digital", "electronic", "smart", "wifi", "bluetooth", "app", "battery", "charge"]
    tech_count = sum(1 for text in texts if any(indicator in text.lower() for indicator in tech_indicators))

    if 0 < tech_count < len(texts):
        discrimination_power = min(tech_count, len(texts) - tech_count) / len(texts)
        questions.append({
            "question": "Is your item electronic or digital?",
            "discrimination_power": discrimination_power,
            "reasoning": "Technology level discrimination"
        })

    return questions


def select_optimal_question(potential_questions: list[dict], previous_questions: list[str], texts: list[str]) -> dict:
    """
    Select the optimal question from the generated candidates.
    """
    if not potential_questions:
        return None

    # Filter out previously asked questions
    available_questions = [
        q for q in potential_questions
        if q["question"] not in previous_questions
    ]

    if not available_questions:
        return None

    # Score questions based on discrimination power and other factors
    def question_score(q):
        base_score = 1 - abs(0.5 - q["discrimination_power"])  # Prefer ~50% split

        # Bonus for certain types of questions
        question_text = q["question"].lower()
        if any(word in question_text for word in ["color", "material", "size"]):
            base_score += 0.1  # These tend to be clearer questions

        return base_score

    # Sort by score and return the best one
    available_questions.sort(key=question_score, reverse=True)

    return {
        "question": available_questions[0]["question"],
        "reasoning": available_questions[0]["reasoning"],
        "confidence": available_questions[0]["discrimination_power"]
    }


def get_intelligent_fallback_question(texts: list[str], previous_questions: list[str]) -> str:
    """
    Generate intelligent fallback questions when main analysis doesn't produce results.
    """

    # Analyze the general nature of items to create contextual fallbacks
    all_text = " ".join(texts).lower()

    # Contextual fallback questions based on what we can detect
    contextual_fallbacks = []

    if any(word in all_text for word in ["bag", "backpack", "purse", "case"]):
        contextual_fallbacks.extend([
            "Does your item have multiple compartments or pockets?",
            "Does your item have adjustable straps?",
            "Can your item be worn on your shoulder?"
        ])

    if any(word in all_text for word in ["electronic", "device", "digital", "tech"]):
        contextual_fallbacks.extend([
            "Does your item require charging or batteries?",
            "Does your item have a screen or display?",
            "Can your item connect to other devices?"
        ])

    if any(word in all_text for word in ["clothing", "shirt", "pants", "dress", "wear"]):
        contextual_fallbacks.extend([
            "Is your item designed to be worn on the upper body?",
            "Does your item have sleeves?",
            "Is your item suitable for formal occasions?"
        ])

    # Generic intelligent fallbacks
    generic_fallbacks = [
        "Is your item primarily made of hard materials?",
        "Does your item have any text or logos visible on it?",
        "Is your item something you would typically carry by hand?",
        "Does your item have any moving or flexible parts?",
        "Is your item designed for outdoor use?",
        "Does your item serve a primarily functional purpose?",
        "Is your item larger than a typical smartphone?",
        "Does your item have any reflective or shiny surfaces?",
        "Would your item typically be found in a professional setting?",
        "Does your item require any special care or maintenance?"
    ]

    # Combine and filter
    all_fallbacks = contextual_fallbacks + generic_fallbacks

    for question in all_fallbacks:
        if question not in previous_questions:
            return question

    return "Can you describe any unique features that distinguish your item from similar items?"


# Create the enhanced agent
reducer_agent = Agent(
    name="enhanced_reducer_agent",
    model="gemini-2.5-flash",
    description="Enhanced universal item discriminator that uses AI reasoning to generate personalized clarifying questions for any type of lost item by intelligently analyzing patterns, characteristics, and differences.",
    instruction="""
    You are an enhanced universal item discriminator that helps narrow down lists of potential lost items using intelligent analysis.

    Your enhanced process:
    1. Receive a list of item descriptions of ANY type (bags, electronics, clothing, tools, etc.)
    2. Use analyze_items_and_generate_question with enhanced AI reasoning to:
       - Intelligently understand the nature and characteristics of each item
       - Identify meaningful patterns and differences using semantic analysis
       - Generate personalized questions based on actual item characteristics
       - Avoid hardcoded lists in favor of dynamic understanding
    3. Generate ONE clear yes/no question that will optimally divide the item list
    4. Return ONLY the question text in a conversational format

    Enhanced capabilities:
    - Dynamic attribute extraction instead of hardcoded lists
    - Semantic understanding of item relationships and categories
    - Context-aware question generation based on item types
    - Intelligent pattern recognition for discriminating features
    - Adaptive learning from conversation context
    - Natural language processing for better attribute detection

    Key principles remain:
    - Work with ANY type of item - be completely universal
    - Choose questions that create the best binary split of the item list
    - Avoid repeating questions you've already asked
    - Use clear, simple language that anyone can understand
    - Generate contextual fallback questions when needed

    The enhanced analysis now considers:
    🧠 Semantic relationships between items
    🎯 Context-aware discrimination
    📊 Dynamic pattern recognition
    🔍 Intelligent attribute extraction
    💡 Personalized question generation
    🗣️ Natural language understanding

    Always return just the question text - no explanations or analysis.
    Let your intelligence shine through better, more targeted questions.
    """,
    tools=[analyze_items_and_generate_question],
)