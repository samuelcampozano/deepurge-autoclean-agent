"""
Deep Intelligence Module for Deepurge AutoClean Agent
Handles content-based analysis for Documents and Images.

Author: Samuel Campozano Lopez
Project: Sui Hackathon 2026
"""
import fitz  # PyMuPDF
from PIL import Image
from pathlib import Path
import re
from typing import Dict, Optional, List

class DeepIntelligence:
    """Provides deep analysis of file contents to improve classification."""
    
    # Keyword categories for Document Intelligence
    DOC_KEYWORDS = {
        "Financial": [r"invoice", r"receipt", r"payment", r"billing", r"tax", r"statement", r"salary", r"nomina"],
        "Work": [r"resume", r"curriculum", r"cv", r"experience", r"employment", r"contract", r"offer"],
        "Academic": [r"university", r"thesis", r"research", r"paper", r"homework", r"exam", r"assignment", r"course"],
        "Legal": [r"agreement", r"terms", r"privacy", r"policy", r"license", r"copyright", r"litigation"]
    }

    @staticmethod
    def analyze_document(file_path: Path) -> Dict:
        """Extracts text and identifies sub-categories for documents."""
        sub_category = "General"
        keywords_found = []
        content_preview = ""

        try:
            if file_path.suffix.lower() == ".pdf":
                doc = fitz.open(str(file_path))
                # Only read the first 2 pages for performance
                text = ""
                for i in range(min(2, len(doc))):
                    text += doc[i].get_text().lower()
                doc.close()
            else:
                # Treat as text file
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    text = f.read(2000).lower()
            
            content_preview = text[:200].replace("\n", " ")

            # Search for category keywords
            for category, patterns in DeepIntelligence.DOC_KEYWORDS.items():
                for pattern in patterns:
                    if re.search(pattern, text):
                        sub_category = category
                        keywords_found.append(pattern)
                        break
                if sub_category != "General":
                    break

        except Exception as e:
            print(f"⚠️ Intel Error (Doc): {e}")

        return {
            "sub_category": sub_category,
            "keywords": keywords_found,
            "preview": content_preview
        }

    @staticmethod
    def analyze_image(file_path: Path) -> Dict:
        """Analyzes image dimensions and metadata to identify usage."""
        sub_category = "General"
        tags = []
        
        try:
            with Image.open(file_path) as img:
                width, height = img.size
                ratio = width / height
                
                # Identify Screenshots (Common desktop aspect ratios)
                if width in [1920, 2560, 3840, 1366] or (ratio > 1.7 and ratio < 1.8):
                    sub_category = "Screenshots"
                # Identify Portraits vs Landscapes
                elif ratio < 0.8:
                    sub_category = "Portraits"
                elif ratio > 1.2:
                    sub_category = "Landscapes"
                
                tags.append(f"{width}x{height}")
                
        except Exception as e:
            print(f"⚠️ Intel Error (Img): {e}")

    @staticmethod
    def get_smart_name(file_path: Path, intelligence: Dict) -> str:
        """Generates a descriptive name based on intelligence data."""
        stem = file_path.stem
        sub = intelligence.get("sub_category", "")
        keywords = intelligence.get("keywords", [])
        
        # Clean stem if it's already a weird download name
        if len(stem) > 20 and any(c.isdigit() for c in stem):
            # If keywords found, use them
            if keywords:
                return f"{sub}_{keywords[0].capitalize()}"
            return f"{sub}_Document"
        
        # Append sub-category if it's high value
        if sub not in ["General", "Other"]:
            return f"{sub}_{stem}"
            
        return stem
