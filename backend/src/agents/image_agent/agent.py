"""
Image generation agent using Gemini 2.5 Flash Image on Vertex AI.
Generates unique, topic-relevant cover images for courses and chapters.
"""
import os
import asyncio
import base64
import uuid
from typing import Dict, Any, Optional
from pathlib import Path
from logging import getLogger

from google import genai
from google.genai import types
from google.adk.sessions import InMemorySessionService

from ..utils import create_text_query, load_instruction_from_file
from ..agent import StandardAgent
from ...config.settings import DEFAULT_COURSE_IMAGE

logger = getLogger(__name__)

# Persistent image storage directory (survives server restarts)
GENERATED_IMAGES_DIR = Path(__file__).parent.parent.parent.parent / "generated_images"
GENERATED_IMAGES_DIR.mkdir(parents=True, exist_ok=True)

# The URL prefix used by the static file mount in main.py
IMAGE_URL_PREFIX = "/api/generated_images"

# Color palettes mapped to broad subject domains for visual variety
DOMAIN_PALETTES = {
    "programming": "deep blue (#1a237e) and electric cyan (#00e5ff) with dark backgrounds",
    "math": "rich purple (#6a1b9a) and golden yellow (#ffd600) with geometric accents",
    "science": "emerald green (#00c853) and bright teal (#00bfa5) with molecular shapes",
    "history": "warm sepia (#8d6e63) and parchment gold (#ffe082) with aged textures",
    "language": "coral orange (#ff6e40) and warm pink (#ff80ab) with flowing curves",
    "business": "navy (#1565c0) and silver (#b0bec5) with clean corporate lines",
    "art": "vibrant magenta (#d500f9) and sunset orange (#ff9100) with creative splashes",
    "music": "deep indigo (#283593) and electric violet (#7c4dff) with wave patterns",
    "health": "fresh green (#66bb6a) and sky blue (#42a5f5) with organic shapes",
    "engineering": "steel gray (#546e7a) and bright amber (#ffab00) with technical elements",
    "default": "teal (#009688) and warm orange (#ff7043) with modern gradients",
}


def _detect_domain(text: str) -> str:
    """Detect the broad subject domain from the content text for palette selection."""
    text_lower = text.lower()
    domain_keywords = {
        "programming": ["python", "java", "code", "programming", "software", "web", "api", "database", "algorithm", "data structure", "javascript", "react", "frontend", "backend", "machine learning", "ai", "deep learning", "neural", "devops", "docker", "git", "sql", "html", "css", "typescript", "rust", "golang", "c++", "kotlin"],
        "math": ["math", "calculus", "algebra", "geometry", "statistics", "probability", "equation", "theorem", "linear", "differential", "integral", "matrix", "number theory"],
        "science": ["physics", "chemistry", "biology", "science", "quantum", "molecule", "atom", "cell", "genetics", "evolution", "ecology", "astronomy", "planet", "space"],
        "history": ["history", "ancient", "medieval", "war", "civilization", "empire", "revolution", "century", "dynasty", "archaeology"],
        "language": ["language", "grammar", "literature", "writing", "english", "spanish", "french", "german", "chinese", "japanese", "linguistics", "vocabulary", "reading"],
        "business": ["business", "marketing", "finance", "economics", "management", "entrepreneurship", "startup", "investment", "accounting", "strategy", "leadership"],
        "art": ["art", "design", "painting", "drawing", "photography", "graphic", "illustration", "sculpture", "creative", "ux", "ui design", "animation"],
        "music": ["music", "piano", "guitar", "singing", "composition", "melody", "rhythm", "instrument", "orchestra", "jazz", "classical"],
        "health": ["health", "medicine", "nutrition", "fitness", "psychology", "mental", "anatomy", "nursing", "pharmacy", "wellness", "yoga", "meditation"],
        "engineering": ["engineering", "mechanical", "electrical", "civil", "robotics", "circuit", "structural", "automotive", "aerospace", "manufacturing"],
    }
    for domain, keywords in domain_keywords.items():
        if any(kw in text_lower for kw in keywords):
            return domain
    return "default"


class ImageAgent(StandardAgent):
    def __init__(self, app_name: str, session_service):
        self.app_name = app_name
        self.session_service = session_service
        self.client = genai.Client()
        self.model_name = "gemini-2.5-flash-image-preview"

        # Load image generation instructions
        instruction_path = os.path.join(os.path.dirname(__file__), "instructions.txt")
        with open(instruction_path, 'r') as f:
            self.instruction = f.read()

    def _build_course_cover_prompt(self, title: str, description: str) -> str:
        """Build a rich, topic-specific prompt for a course cover image."""
        domain = _detect_domain(f"{title} {description}")
        palette = DOMAIN_PALETTES.get(domain, DOMAIN_PALETTES["default"])

        return f"""{self.instruction}

Generate a UNIQUE cover image for this specific course:

COURSE TITLE: {title}
COURSE DESCRIPTION: {description}

VISUAL REQUIREMENTS:
- Depict recognizable symbols and icons that directly represent "{title}"
- Use a flat illustration / vector art style with bold, clean shapes
- Color palette: {palette}
- 16:9 landscape composition with a clear central focal point
- Soft gradient background that complements the subject icons
- NO text, NO letters, NO words, NO watermarks anywhere in the image
- Professional quality suitable as a course thumbnail on an e-learning platform
- The image should make someone immediately understand what the course is about just by looking at it

IMPORTANT: Make this image UNIQUE to this specific topic. Do NOT create a generic education image."""

    def _build_chapter_image_prompt(self, chapter_caption: str, chapter_content: str, course_title: str) -> str:
        """Build a topic-specific prompt for a chapter cover image."""
        combined = f"{course_title} {chapter_caption} {chapter_content}"
        domain = _detect_domain(combined)
        palette = DOMAIN_PALETTES.get(domain, DOMAIN_PALETTES["default"])

        # Truncate content to avoid token limits
        content_preview = chapter_content[:300] if len(chapter_content) > 300 else chapter_content

        return f"""{self.instruction}

Generate a UNIQUE illustration for this specific chapter:

COURSE: {course_title}
CHAPTER TITLE: {chapter_caption}
CHAPTER TOPICS: {content_preview}

VISUAL REQUIREMENTS:
- Show visual elements and icons that specifically represent "{chapter_caption}"
- This must look DIFFERENT from other chapters in the same course
- Use flat illustration / vector art style
- Color palette: {palette} (but use a slightly different shade/accent than the course cover)
- 16:9 landscape composition
- Soft gradient background
- NO text, NO letters, NO words, NO watermarks
- Clean, modern, and professional

IMPORTANT: The image must be visually distinct and specific to THIS chapter's topic, not a generic education image."""

    async def generate_image(self, prompt: str, output_path: str) -> str:
        """Generate an image using Gemini 2.5 Flash Image and save to disk."""
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=1.0,
                candidate_count=1,
            )
        )

        if response.candidates and len(response.candidates) > 0:
            candidate = response.candidates[0]
            for part in candidate.content.parts:
                if hasattr(part, 'inline_data') and part.inline_data:
                    image_data = part.inline_data.data
                    os.makedirs(os.path.dirname(output_path), exist_ok=True)
                    with open(output_path, 'wb') as f:
                        f.write(image_data)
                    logger.info("Image saved to %s (%d bytes)", output_path, len(image_data))
                    return output_path

        raise ValueError("No image data found in Gemini response")

    async def run(self, user_id: str, state: Dict[str, Any], content: str,
                  image_type: str = "course",
                  title: str = "", description: str = "",
                  chapter_caption: str = "", chapter_content: str = "",
                  course_title: str = "") -> Dict[str, Any]:
        """
        Run the image generation agent.

        Args:
            user_id: User identifier
            state: Current state dictionary
            content: Fallback text content (used if title/chapter_caption not provided)
            image_type: "course" for course covers, "chapter" for chapter images
            title: Course title (for course covers)
            description: Course description (for course covers)
            chapter_caption: Chapter title (for chapter images)
            chapter_content: Chapter content summary (for chapter images)
            course_title: Parent course title (for chapter images, for context)

        Returns:
            Dictionary containing the generated image URL
        """
        # Build the appropriate prompt
        if image_type == "chapter" and chapter_caption:
            prompt = self._build_chapter_image_prompt(chapter_caption, chapter_content or content, course_title)
        elif title:
            prompt = self._build_course_cover_prompt(title, description or content)
        else:
            # Fallback: use content directly with course cover style
            prompt = self._build_course_cover_prompt(content, "")

        # Generate a unique filename using UUID (prevents collisions & reuse of old images)
        filename = f"{image_type}_{user_id}_{uuid.uuid4().hex[:12]}.png"
        output_path = str(GENERATED_IMAGES_DIR / filename)

        try:
            await self.generate_image(prompt, output_path)

            # Return a URL path that the frontend can use (served by FastAPI static mount)
            image_url = f"{IMAGE_URL_PREFIX}/{filename}"
            logger.info("Image generated successfully: %s", image_url)

            return {
                "status": "success",
                "url": image_url,
                "explanation": image_url,
                "image_path": output_path,
                "user_id": user_id,
                "prompt": content
            }
        except Exception as e:
            logger.error("Image generation failed: %s", str(e))
            return {
                "status": "error",
                "error": str(e),
                "url": DEFAULT_COURSE_IMAGE,
                "explanation": DEFAULT_COURSE_IMAGE,
                "fallback_url": DEFAULT_COURSE_IMAGE
            }


async def main():
    print("Starting ImageAgent test")
    image_agent_instance = ImageAgent(app_name="LearnWeave", session_service=InMemorySessionService())

    # Test course cover
    response = await image_agent_instance.run(
        user_id="test",
        state={},
        content="",
        image_type="course",
        title="Python Data Structures & Algorithms",
        description="Master fundamental data structures like trees, graphs, and hash maps, and learn classic algorithms for sorting, searching, and optimization."
    )
    print("Course cover:", response)

    # Test chapter image
    response = await image_agent_instance.run(
        user_id="test",
        state={},
        content="",
        image_type="chapter",
        chapter_caption="Binary Search Trees",
        chapter_content="Understanding BST operations: insertion, deletion, traversal. Balanced trees and AVL rotations.",
        course_title="Python Data Structures & Algorithms"
    )
    print("Chapter image:", response)

if __name__ == "__main__":
    asyncio.run(main())