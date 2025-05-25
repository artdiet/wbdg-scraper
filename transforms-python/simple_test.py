#!/usr/bin/env python3
"""
Simple test to verify the WBDG scraper works correctly.
"""

import sys
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, 'src')

from myproject.datasets.wbdg_scraper import WBDGScraper


def test_basic_functionality():
    """Test basic scraper functionality."""
    print("=== Testing WBDG Scraper Basic Functionality ===")
    
    # Create temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"Using temporary directory: {temp_dir}")
        
        # Initialize scraper
        scraper = WBDGScraper(
            base_url="https://www.wbdg.org/",
            output_dir=temp_dir,
            log_level="INFO"
        )
        
        print("✓ Scraper initialized successfully")
        
        # Check directory creation
        assert scraper.pdfs_dir.exists()
        assert scraper.logs_dir.exists()
        print("✓ Output directories created")
        
        # Test PDF validation
        valid_pdf = b"%PDF-1.4\ntest content\n%%EOF"
        invalid_content = b"not a pdf"
        
        # Mock PDF validation since we don't want complex PDF creation
        from unittest.mock import patch
        
        with patch('myproject.datasets.wbdg_scraper.PdfReader') as mock_reader:
            mock_reader.return_value = True
            assert scraper._validate_pdf(valid_pdf) is True
            print("✓ PDF validation working")
        
        with patch('myproject.datasets.wbdg_scraper.PdfReader') as mock_reader:
            mock_reader.side_effect = Exception("Invalid PDF")
            assert scraper._validate_pdf(invalid_content) is False
            print("✓ Invalid PDF rejection working")
        
        # Test logging
        scraper._log_event("test_event", {"key": "value"})
        assert len(scraper.log_entries) == 1
        assert scraper.log_entries[0]["event_type"] == "test_event"
        print("✓ Event logging working")
        
        # Test log saving
        scraper.save_crawl_log()
        log_file = scraper.logs_dir / "crawl_log.json"
        assert log_file.exists()
        print("✓ Log file saving working")
        
        print("\n🎉 All basic functionality tests passed!")
        
        return True


def test_cli_interface():
    """Test command line interface."""
    print("\n=== Testing CLI Interface ===")
    
    import subprocess
    import os
    
    # Test help command
    env = os.environ.copy()
    env['PYTHONPATH'] = 'src'
    
    result = subprocess.run([
        'python', '-m', 'myproject.datasets.wbdg_scraper', '--help'
    ], env=env, capture_output=True, text=True)
    
    if result.returncode == 0:
        print("✓ CLI help command working")
        assert "--base-url" in result.stdout
        assert "--output-dir" in result.stdout
        assert "--crawl-only" in result.stdout
        print("✓ CLI arguments properly defined")
    else:
        print(f"✗ CLI help failed: {result.stderr}")
        return False
    
    print("\n🎉 CLI interface tests passed!")
    return True


def main():
    """Run all tests."""
    print("Starting WBDG Scraper Tests...\n")
    
    try:
        # Test basic functionality
        if not test_basic_functionality():
            print("❌ Basic functionality tests failed")
            return 1
        
        # Test CLI interface
        if not test_cli_interface():
            print("❌ CLI interface tests failed")
            return 1
        
        print("\n" + "="*50)
        print("🎉 ALL TESTS PASSED! 🎉")
        print("The WBDG scraper is ready for deployment.")
        print("="*50)
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())