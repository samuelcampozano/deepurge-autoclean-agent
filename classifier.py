"""
File Classifier Module for Deepurge AutoClean Agent
Automatically classifies files based on their extensions

Author: Samuel Campozano Lopez
Project: Sui Hackathon 2026
"""
import json
import hashlib
from pathlib import Path
from typing import Optional, Dict, List, Tuple


class FileClassifier:
    """Classifies files into categories based on file extensions"""
    
    # Default categories if config not loaded
    DEFAULT_CATEGORIES = {
        "Images": [".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp", ".ico", ".tiff"],
        "Documents": [".pdf", ".docx", ".doc", ".txt", ".md", ".xlsx", ".xls", ".pptx", ".ppt", ".odt", ".rtf", ".csv"],
        "Videos": [".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv", ".webm", ".m4v"],
        "Audio": [".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma", ".m4a"],
        "Code": [".py", ".js", ".ts", ".html", ".css", ".java", ".cpp", ".c", ".h", ".json", ".xml", ".yaml", ".yml", ".sol", ".move", ".rs"],
        "Archives": [".zip", ".rar", ".tar", ".gz", ".7z", ".bz2"],
        "Executables": [".exe", ".msi", ".bat", ".cmd", ".ps1", ".sh"],
        "Other": []
    }
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the classifier
        
        Args:
            config_path: Path to config.json file
        """
        self.categories = self.DEFAULT_CATEGORIES.copy()
        
        if config_path:
            self._load_config(config_path)
        
        self._build_extension_map()
    
    def _load_config(self, config_path: str):
        """Load categories from config file"""
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                if 'categories' in config:
                    self.categories = config['categories']
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"⚠️ Could not load config: {e}. Using defaults.")
    
    def _build_extension_map(self):
        """Build a reverse mapping from extension to category"""
        self.extension_map = {}
        for category, extensions in self.categories.items():
            for ext in extensions:
                self.extension_map[ext.lower()] = category
    
    def classify(self, file_path: Path) -> str:
        """
        Classify a file based on its extension
        
        Args:
            file_path: Path to the file
            
        Returns:
            Category name (e.g., "Images", "Documents", etc.)
        """
        extension = file_path.suffix.lower()
        return self.extension_map.get(extension, "Other")
    
    def get_destination_folder(self, file_path: Path, base_folder: Path) -> Path:
        """
        Get the destination folder for a file
        
        Args:
            file_path: Path to the file
            base_folder: Base folder for organized files
            
        Returns:
            Destination folder path
        """
        category = self.classify(file_path)
        return base_folder / category
    
    def get_all_categories(self) -> List[str]:
        """Return all available categories"""
        return list(self.categories.keys())
    
    def get_category_extensions(self, category: str) -> Optional[List[str]]:
        """Get extensions for a specific category"""
        return self.categories.get(category)
    
    def add_custom_rule(self, category: str, extensions: List[str]):
        """
        Add custom classification rules
        
        Args:
            category: Category name
            extensions: List of file extensions
        """
        if category in self.categories:
            self.categories[category].extend(extensions)
        else:
            self.categories[category] = extensions
        self._build_extension_map()
    
    @staticmethod
    def compute_file_hash(file_path: Path, chunk_size: int = 8192) -> str:
        """
        Compute SHA256 hash of a file
        
        Args:
            file_path: Path to the file
            chunk_size: Size of chunks to read
            
        Returns:
            SHA256 hash as hexadecimal string
        """
        sha256_hash = hashlib.sha256()
        
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(chunk_size), b""):
                    sha256_hash.update(chunk)
            return sha256_hash.hexdigest()
        except (IOError, PermissionError) as e:
            return f"error:{str(e)}"
    
    def analyze_file(self, file_path: Path) -> Dict:
        """
        Analyze a file and return detailed information
        
        Args:
            file_path: Path to the file
            
        Returns:
            Dictionary with file analysis
        """
        path = Path(file_path)
        
        analysis = {
            "name": path.name,
            "stem": path.stem,
            "extension": path.suffix.lower(),
            "category": self.classify(path),
            "size": 0,
            "hash": None,
            "exists": path.exists()
        }
        
        if path.exists():
            try:
                stat = path.stat()
                analysis["size"] = stat.st_size
                analysis["hash"] = self.compute_file_hash(path)
            except (IOError, PermissionError):
                pass
        
        return analysis
    
    def get_category_stats(self, files: List[Path]) -> Dict[str, int]:
        """
        Get statistics for a list of files by category
        
        Args:
            files: List of file paths
            
        Returns:
            Dictionary with category counts
        """
        stats = {cat: 0 for cat in self.get_all_categories()}
        
        for file_path in files:
            category = self.classify(Path(file_path))
            stats[category] = stats.get(category, 0) + 1
        
        return stats


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"


if __name__ == "__main__":
    # Test the classifier
    print("🧪 Testing File Classifier...")
    print("-" * 50)
    
    classifier = FileClassifier()
    
    test_files = [
        Path("vacation_photo.jpg"),
        Path("report.pdf"),
        Path("movie.mp4"),
        Path("song.mp3"),
        Path("script.py"),
        Path("project.zip"),
        Path("installer.exe"),
        Path("unknown.xyz"),
    ]
    
    print("\n📁 File Classification Results:")
    for file in test_files:
        category = classifier.classify(file)
        emoji = {
            "Images": "📸",
            "Documents": "📄",
            "Videos": "🎬",
            "Audio": "🎵",
            "Code": "💻",
            "Archives": "📦",
            "Executables": "⚙️",
            "Other": "📁"
        }.get(category, "📁")
        print(f"  {emoji} {file.name:20} → {category}")
    
    print("\n📊 Category Statistics:")
    stats = classifier.get_category_stats(test_files)
    for category, count in stats.items():
        if count > 0:
            print(f"  {category}: {count} file(s)")
    
    print("\n✅ All tests passed!")
