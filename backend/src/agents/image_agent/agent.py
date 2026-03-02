"""
Image generation agent using styled HTML-to-image conversion.
Generates unique, topic-relevant cover images for courses and chapters using gradients and typography.
"""
import os
import asyncio
import uuid
import hashlib
from typing import Dict, Any, Optional
from pathlib import Path
from logging import getLogger
import base64

from google.adk.sessions import InMemorySessionService

from ..utils import create_text_query
from ..agent import StandardAgent
from ...config.settings import DEFAULT_COURSE_IMAGE, USE_CLOUD_STORAGE
from ...services.storage_service import StorageService

logger = getLogger(__name__)

# Persistent image storage directory (local development fallback)
GENERATED_IMAGES_DIR = Path(__file__).parent.parent.parent.parent / "generated_images"
GENERATED_IMAGES_DIR.mkdir(parents=True, exist_ok=True)

# The URL prefix used by the static file mount in main.py
IMAGE_URL_PREFIX = "/api/generated_images"

# Initialize storage service for cloud-aware image saving
_storage_service = None

def _get_storage_service():
    global _storage_service
    if _storage_service is None:
        _storage_service = StorageService()
    return _storage_service

# Color palettes mapped to broad subject domains for visual variety
DOMAIN_PALETTES = {
    "programming": {"primary": "#1a237e", "secondary": "#00e5ff", "accent": "#7c4dff"},
    "math": {"primary": "#6a1b9a", "secondary": "#ffd600", "accent": "#aa00ff"},
    "science": {"primary": "#00695c", "secondary": "#00e676", "accent": "#1de9b6"},
    "history": {"primary": "#5d4037", "secondary": "#ffab00", "accent": "#ff6f00"},
    "language": {"primary": "#d32f2f", "secondary": "#ff80ab", "accent": "#f50057"},
    "business": {"primary": "#0d47a1", "secondary": "#64b5f6", "accent": "#2196f3"},
    "art": {"primary": "#6a1b9a", "secondary": "#ff9800", "accent": "#e91e63"},
    "music": {"primary": "#311b92", "secondary": "#7c4dff", "accent": "#d500f9"},
    "health": {"primary": "#1b5e20", "secondary": "#76ff03", "accent": "#00e676"},
    "engineering": {"primary": "#263238", "secondary": "#ffab00", "accent": "#607d8b"},
    "default": {"primary": "#00796b", "secondary": "#ff6e40", "accent": "#26a69a"},
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

        # Load image generation instructions
        instruction_path = os.path.join(os.path.dirname(__file__), "instructions.txt")
        with open(instruction_path, 'r') as f:
            self.instruction = f.read()

    def _get_domain_icons(self, domain: str, hash_val: int) -> str:
        """Generate domain-specific SVG icon elements."""
        icons = {
            "programming": f'''
  <!-- Code brackets and symbols -->
  <path d="M 300 350 L 250 450 L 300 550" stroke="white" stroke-width="12" fill="none" opacity="0.4"/>
  <path d="M 1300 350 L 1350 450 L 1300 550" stroke="white" stroke-width="12" fill="none" opacity="0.4"/>
  <circle cx="400" cy="300" r="25" fill="white" opacity="0.3"/>
  <circle cx="500" cy="250" r="20" fill="white" opacity="0.3"/>
  <circle cx="1200" cy="320" r="25" fill="white" opacity="0.3"/>
  <rect x="350" y="600" width="120" height="15" fill="white" opacity="0.25" rx="5"/>
  <rect x="1130" y="620" width="100" height="15" fill="white" opacity="0.25" rx="5"/>
  <text x="250" y="700" font-family="monospace" font-size="100" fill="white" opacity="0.15">&lt;/&gt;</text>''',
            
            "math": f'''
  <!-- Math symbols and geometric shapes -->
  <circle cx="280" cy="300" r="80" stroke="white" stroke-width="8" fill="none" opacity="0.3"/>
  <rect x="1200" y="500" width="120" height="120" stroke="white" stroke-width="8" fill="none" opacity="0.3" transform="rotate({hash_val % 45} 1260 560)"/>
  <path d="M 200 600 L 300 600 M 250 570 L 250 630" stroke="white" stroke-width="10" opacity="0.35"/>
  <text x="1250" y="350" font-family="serif" font-size="140" fill="white" opacity="0.2">π</text>
  <text x="320" y="750" font-family="serif" font-size="100" fill="white" opacity="0.2">∑</text>
  <polygon points="1300,200 1380,320 1220,320" stroke="white" stroke-width="6" fill="none" opacity="0.25"/>''',
            
            "science": f'''
  <!-- Molecules and atoms -->
  <circle cx="300" cy="300" r="40" fill="white" opacity="0.4"/>
  <circle cx="400" cy="280" r="35" fill="white" opacity="0.35"/>
  <circle cx="350" cy="380" r="30" fill="white" opacity="0.3"/>
  <line x1="300" y1="300" x2="400" y2="280" stroke="white" stroke-width="6" opacity="0.3"/>
  <line x1="300" y1="300" x2="350" y2="380" stroke="white" stroke-width="6" opacity="0.3"/>
  <circle cx="1250" cy="250" r="50" stroke="white" stroke-width="8" fill="none" opacity="0.3"/>
  <circle cx="1250" cy="250" r="30" stroke="white" stroke-width="4" fill="none" opacity="0.25"/>
  <circle cx="1250" cy="250" r="10" fill="white" opacity="0.4"/>
  <path d="M 250 650 Q 300 600, 350 650 T 450 650" stroke="white" stroke-width="8" fill="none" opacity="0.25"/>''',
            
            "history": f'''
  <!-- Ancient pillars and scrolls -->
  <rect x="250" y="300" width="40" height="300" fill="white" opacity="0.25" rx="5"/>
  <rect x="320" y="300" width="40" height="300" fill="white" opacity="0.25" rx="5"/>
  <rect x="220" y="280" width="170" height="25" fill="white" opacity="0.3"/>
  <path d="M 1200 400 Q 1250 380, 1300 400 L 1300 550 Q 1250 570, 1200 550 Z" fill="white" opacity="0.25"/>
  <line x1="1220" y1="430" x2="1280" y2="430" stroke="rgba(0,0,0,0.3)" stroke-width="3"/>
  <line x1="1220" y1="470" x2="1280" y2="470" stroke="rgba(0,0,0,0.3)" stroke-width="3"/>
  <line x1="1220" y1="510" x2="1280" y2="510" stroke="rgba(0,0,0,0.3)" stroke-width="3"/>''',
            
            "language": f'''
  <!-- Speech bubbles and letters -->
  <path d="M 250 300 Q 250 250, 300 250 L 450 250 Q 500 250, 500 300 L 500 400 Q 500 450, 450 450 L 320 450 L 280 500 L 290 450 L 300 450 Q 250 450, 250 400 Z" fill="white" opacity="0.25"/>
  <text x="300" y="370" font-family="Arial" font-size="90" fill="rgba(0,0,0,0.4)" font-weight="bold">Aa</text>
  <circle cx="1280" cy="350" r="90" fill="white" opacity="0.2"/>
  <text x="1240" y="385" font-family="Arial" font-size="80" fill="rgba(0,0,0,0.5)" font-weight="bold">文</text>''',
            
            "business": f'''
  <!-- Charts and graphs -->
  <rect x="250" y="450" width="60" height="200" fill="white" opacity="0.3"/>
  <rect x="330" y="350" width="60" height="300" fill="white" opacity="0.35"/>
  <rect x="410" y="400" width="60" height="250" fill="white" opacity="0.25"/>
  <path d="M 1150 550 L 1200 480 L 1260 510 L 1320 420" stroke="white" stroke-width="12" fill="none" opacity="0.35"/>
  <circle cx="1150" cy="550" r="15" fill="white" opacity="0.4"/>
  <circle cx="1200" cy="480" r="15" fill="white" opacity="0.4"/>
  <circle cx="1260" cy="510" r="15" fill="white" opacity="0.4"/>
  <circle cx="1320" cy="420" r="15" fill="white" opacity="0.4"/>''',
            
            "art": f'''
  <!-- Palette and brush strokes -->
  <ellipse cx="280" cy="350" rx="100" ry="80" fill="white" opacity="0.25"/>
  <circle cx="250" cy="320" r="25" fill="rgba(255,100,100,0.5)"/>
  <circle cx="310" cy="320" r="25" fill="rgba(100,255,100,0.5)"/>
  <circle cx="280" cy="380" r="25" fill="rgba(100,100,255,0.5)"/>
  <path d="M 1200 300 Q 1250 250, 1300 300 Q 1350 350, 1300 400" stroke="white" stroke-width="20" fill="none" opacity="0.3" stroke-linecap="round"/>
  <path d="M 1220 550 Q 1260 500, 1320 530" stroke="white" stroke-width="18" fill="none" opacity="0.25" stroke-linecap="round"/>''',
            
            "music": f'''
  <!-- Musical notes -->
  <circle cx="300" cy="450" r="40" fill="white" opacity="0.35"/>
  <rect x="335" y="300" width="12" height="150" fill="white" opacity="0.35"/>
  <circle cx="400" cy="480" r="40" fill="white" opacity="0.3"/>
  <rect x="435" y="320" width="12" height="160" fill="white" opacity="0.3"/>
  <path d="M 335 310 Q 380 290, 447 310" stroke="white" stroke-width="14" fill="none" opacity="0.35"/>
  <circle cx="1260" cy="350" r="100" stroke="white" stroke-width="10" fill="none" opacity="0.25"/>
  <path d="M 1210 350 L 1310 350 M 1260 300 L 1260 400" stroke="white" stroke-width="8" opacity="0.3"/>''',
            
            "health": f'''
  <!-- Medical cross and heart -->
  <path d="M 290 300 L 290 600 M 190 450 L 390 450" stroke="white" stroke-width="50" opacity="0.25"/>
  <path d="M 1260 300 Q 1210 250, 1160 300 Q 1160 350, 1260 450 Q 1360 350, 1360 300 Q 1310 250, 1260 300" fill="white" opacity="0.25"/>
  <circle cx="1260" cy="600" r="60" stroke="white" stroke-width="10" fill="none" opacity="0.2"/>
  <path d="M 1240 580 L 1250 595 L 1280 565" stroke="white" stroke-width="8" fill="none" opacity="0.25"/>''',
            
            "engineering": f'''
  <!-- Gears and tools -->
  <circle cx="300" cy="400" r="80" stroke="white" stroke-width="12" fill="none" opacity="0.3"/>
  <circle cx="300" cy="400" r="40" fill="white" opacity="0.2"/>
  <rect x="260" y="320" width="80" height="160" fill="none" stroke="white" stroke-width="10" opacity="0.25"/>
  <circle cx="1280" cy="400" r="90" stroke="white" stroke-width="14" fill="none" opacity="0.3"/>
  <path d="M 1280 310 L 1300 330 L 1320 310 L 1340 330 L 1360 310 L 1380 330 L 1390 350" stroke="white" stroke-width="8" fill="none" opacity="0.25"/>
  <rect x="1230" y="550" width="100" height="60" fill="white" opacity="0.2" rx="5"/>''',
            
            "default": f'''
  <!-- Abstract shapes for general topics -->
  <circle cx="300" cy="350" r="70" stroke="white" stroke-width="10" fill="none" opacity="0.3"/>
  <rect x="1180" y="280" width="140" height="140" stroke="white" stroke-width="10" fill="none" opacity="0.25" rx="20"/>
  <polygon points="400,600 480,720 320,720" stroke="white" stroke-width="8" fill="none" opacity="0.3"/>
  <circle cx="1250" cy="550" r="50" fill="white" opacity="0.2"/>
  <path d="M 250 200 Q 300 150, 350 200" stroke="white" stroke-width="10" fill="none" opacity="0.25"/>'''
        }
        
        return icons.get(domain, icons["default"])

    def _generate_svg_image(self, title: str, domain: str, seed: str, image_type: str) -> str:
        """Generate a unique SVG image with gradients and domain-specific visual elements."""
        palette = DOMAIN_PALETTES.get(domain, DOMAIN_PALETTES["default"])
        
        # Use seed to generate consistent but unique patterns for each image
        hash_val = int(hashlib.md5(seed.encode()).hexdigest()[:8], 16)
        
        # Generate unique pattern variations based on hash
        angle = (hash_val % 360)
        opacity = 0.08 + ((hash_val % 8) / 100)
        
        # Truncate title if too long
        display_title = title[:55] + "..." if len(title) > 55 else title
        
        # Escape XML special characters in title
        display_title = display_title.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
        
        # Get domain-specific decorative elements
        domain_icons = self._get_domain_icons(domain, hash_val)
        
        svg = f'''<svg width="1600" height="900" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="grad1" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:{palette['primary']};stop-opacity:1" />
      <stop offset="50%" style="stop-color:{palette['secondary']};stop-opacity:0.9" />
      <stop offset="100%" style="stop-color:{palette['accent']};stop-opacity:1" />
    </linearGradient>
    <radialGradient id="glow" cx="50%" cy="50%">
      <stop offset="0%" style="stop-color:white;stop-opacity:0.3" />
      <stop offset="100%" style="stop-color:white;stop-opacity:0" />
    </radialGradient>
  </defs>
  
  <!-- Background -->
  <rect width="1600" height="900" fill="url(#grad1)"/>
  
  <!-- Glow effect -->
  <ellipse cx="800" cy="450" rx="600" ry="300" fill="url(#glow)"/>
  
  <!-- Domain-specific decorative icons -->
{domain_icons}
  
  <!-- Decorative bottom line -->
  <rect x="600" y="600" width="400" height="4" fill="white" opacity="0.3" rx="2"/>
  
  <!-- Title container background -->
  <rect x="200" y="380" width="1200" height="140" fill="rgba(0,0,0,0.2)" rx="20"/>
  
  <!-- Title -->
  <text x="800" y="470" font-family="'Segoe UI', Arial, sans-serif" font-size="68" font-weight="bold" 
        fill="white" text-anchor="middle" opacity="0.98">
    {display_title}
  </text>
  
  <!-- Type badge -->
  <rect x="720" y="540" width="160" height="40" fill="rgba(255,255,255,0.2)" rx="20"/>
  <text x="800" y="568" font-family="Arial, sans-serif" font-size="24" font-weight="600"
        fill="white" text-anchor="middle" opacity="0.9">
    {image_type.upper()}
  </text>
</svg>'''
        
        return svg

    async def generate_image(self, title: str, domain: str, seed: str, image_type: str, output_path: str) -> str:
        """Generate an SVG image and save it to disk (local fallback)."""
        svg_content = self._generate_svg_image(title, domain, seed, image_type)
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(svg_content)
        
        logger.info("SVG image saved to %s", output_path)
        return output_path

    async def generate_image_cloud(self, title: str, domain: str, seed: str, image_type: str, filename: str) -> str:
        """Generate an SVG image and save it to cloud storage. Returns the public URL."""
        svg_content = self._generate_svg_image(title, domain, seed, image_type)
        svg_bytes = svg_content.encode('utf-8')
        
        storage = _get_storage_service()
        # Upload to GCS and get public URL
        blob = storage.bucket_images.blob(filename)
        blob.upload_from_string(svg_bytes, content_type='image/svg+xml')
        blob.make_public()
        url = blob.public_url
        
        logger.info("SVG image uploaded to cloud storage: %s", url)
        return url

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
        # Determine the title and detect domain
        if image_type == "chapter" and chapter_caption:
            display_title = chapter_caption
            combined = f"{course_title} {chapter_caption} {chapter_content}"
            seed = f"{chapter_caption}_{user_id}_{uuid.uuid4().hex[:8]}"
        elif title:
            display_title = title
            combined = f"{title} {description}"
            seed = f"{title}_{user_id}_{uuid.uuid4().hex[:8]}"
        else:
            display_title = content[:50]
            combined = content
            seed = f"{content}_{user_id}_{uuid.uuid4().hex[:8]}"
        
        domain = _detect_domain(combined)
        
        # Generate a unique filename using UUID
        filename = f"{image_type}_{user_id}_{uuid.uuid4().hex[:12]}.svg"

        try:
            # Use cloud storage in production, local filesystem in development
            if USE_CLOUD_STORAGE:
                try:
                    image_url = await self.generate_image_cloud(display_title, domain, seed, image_type, filename)
                    logger.info("Image generated and uploaded to cloud: %s", image_url)
                except Exception as cloud_err:
                    logger.warning("Cloud storage upload failed, falling back to data URI: %s", str(cloud_err))
                    # Fallback: encode SVG as data URI so it survives container restarts
                    svg_content = self._generate_svg_image(display_title, domain, seed, image_type)
                    svg_b64 = base64.b64encode(svg_content.encode('utf-8')).decode('utf-8')
                    image_url = f"data:image/svg+xml;base64,{svg_b64}"
            else:
                output_path = str(GENERATED_IMAGES_DIR / filename)
                await self.generate_image(display_title, domain, seed, image_type, output_path)
                image_url = f"{IMAGE_URL_PREFIX}/{filename}"

            logger.info("Image generated successfully: %s", image_url[:100])

            return {
                "status": "success",
                "url": image_url,
                "explanation": image_url,
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