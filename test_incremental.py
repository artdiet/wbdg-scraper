#!/usr/bin/env python3
"""
Test script to demonstrate incremental download functionality.
"""

import sys
import tempfile
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, 'src')

from myproject.datasets.wbdg_scraper import WBDGScraper
import responses
from unittest.mock import patch


def test_incremental_downloads():
    """Test incremental download functionality with mock data."""
    print("=== Testing Incremental Download Functionality ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"Using temporary directory: {temp_dir}")
        
        # Initialize scraper
        scraper = WBDGScraper(
            base_url="https://test.wbdg.org/",
            output_dir=temp_dir,
            log_level="INFO"
        )
        
        # Mock HTML content
        html_content = """
        <html>
            <body>
                <a href="UFC-1-200-01.pdf">UFC 1-200-01</a>
                <a href="UFC-3-230-01.pdf">UFC 3-230-01</a>
            </body>
        </html>
        """
        
        # Create fake PDF content
        pdf_content_1 = b"%PDF-1.4\nUFC-1-200-01 content\n%%EOF"
        pdf_content_2 = b"%PDF-1.4\nUFC-3-230-01 content\n%%EOF"
        
        with responses.RequestsMock() as rsps:
            # Mock crawl page
            rsps.add(
                responses.GET,
                "https://test.wbdg.org/dod/ufc",
                body=html_content,
                status=200
            )
            
            # Mock PDF files - first run
            for filename, content in [("UFC-1-200-01.pdf", pdf_content_1), 
                                    ("UFC-3-230-01.pdf", pdf_content_2)]:
                url = f"https://test.wbdg.org/dod/{filename}"
                
                # HEAD request
                rsps.add(
                    responses.HEAD,
                    url,
                    headers={
                        "content-length": str(len(content)),
                        "last-modified": "Wed, 01 Jan 2025 00:00:00 GMT"
                    },
                    status=200
                )
                
                # GET request
                rsps.add(
                    responses.GET,
                    url,
                    body=content,
                    status=200
                )
            
            print("\n--- First Run (Initial Download) ---")
            with patch.object(scraper, '_validate_pdf', return_value=True):
                summary1 = scraper.run_full_scrape()
            
            print(f"✓ Downloaded {summary1['success_count']} files")
            print(f"✓ Skipped {summary1['skipped_count']} files")
            print(f"✓ Tracking {summary1['total_files_tracked']} files")
            
            # Verify files exist
            assert (scraper.pdfs_dir / "UFC-1-200-01.pdf").exists()
            assert (scraper.pdfs_dir / "UFC-3-230-01.pdf").exists()
            
            # Verify metadata exists
            assert scraper.metadata_file.exists()
            assert len(scraper.file_metadata) == 2
            
        # Second run - no changes (should skip all)
        with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
            # Mock crawl page (same)
            rsps.add(
                responses.GET,
                "https://test.wbdg.org/dod/ufc",
                body=html_content,
                status=200
            )
            
            # Mock PDF HEAD requests (same content)
            for filename, content in [("UFC-1-200-01.pdf", pdf_content_1), 
                                    ("UFC-3-230-01.pdf", pdf_content_2)]:
                url = f"https://test.wbdg.org/dod/{filename}"
                
                rsps.add(
                    responses.HEAD,
                    url,
                    headers={
                        "content-length": str(len(content)),
                        "last-modified": "Wed, 01 Jan 2025 00:00:00 GMT"
                    },
                    status=200
                )
            
            print("\n--- Second Run (No Changes) ---")
            with patch.object(scraper, '_validate_pdf', return_value=True):
                summary2 = scraper.run_full_scrape()
            
            print(f"✓ Downloaded {summary2['success_count']} new files")
            print(f"✓ Skipped {summary2['skipped_count']} unchanged files")
            print(f"✓ Tracking {summary2['total_files_tracked']} total files")
            
            # Should skip all files
            assert summary2['success_count'] == 0
            assert summary2['skipped_count'] == 2
            
        # Third run - one file changed
        pdf_content_1_updated = b"%PDF-1.4\nUFC-1-200-01 UPDATED content\n%%EOF"
        
        with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
            # Mock crawl page (same)
            rsps.add(
                responses.GET,
                "https://test.wbdg.org/dod/ufc",
                body=html_content,
                status=200
            )
            
            # Mock PDF HEAD requests - one changed
            files_data = [
                ("UFC-1-200-01.pdf", pdf_content_1_updated, "Thu, 02 Jan 2025 00:00:00 GMT"),
                ("UFC-3-230-01.pdf", pdf_content_2, "Wed, 01 Jan 2025 00:00:00 GMT")
            ]
            
            for filename, content, last_modified in files_data:
                url = f"https://test.wbdg.org/dod/{filename}"
                
                rsps.add(
                    responses.HEAD,
                    url,
                    headers={
                        "content-length": str(len(content)),
                        "last-modified": last_modified
                    },
                    status=200
                )
                
                # Only add GET for the changed file
                if "UPDATED" in content.decode():
                    rsps.add(
                        responses.GET,
                        url,
                        body=content,
                        status=200
                    )
            
            print("\n--- Third Run (One File Changed) ---")
            with patch.object(scraper, '_validate_pdf', return_value=True):
                summary3 = scraper.run_full_scrape()
            
            print(f"✓ Downloaded {summary3['success_count']} new/changed files")
            print(f"✓ Skipped {summary3['skipped_count']} unchanged files")
            print(f"✓ Tracking {summary3['total_files_tracked']} total files")
            
            # Should download 1, skip 1
            assert summary3['success_count'] == 1
            assert summary3['skipped_count'] == 1
            
            # Verify updated content
            updated_content = (scraper.pdfs_dir / "UFC-1-200-01.pdf").read_bytes()
            assert b"UPDATED" in updated_content
        
        # Test status command
        print("\n--- Status Check ---")
        status = scraper.get_incremental_status()
        print(f"✓ Status: {status['status']}")
        print(f"✓ Total files: {status['total_files']}")
        print(f"✓ Total size: {status['total_size_mb']} MB")
        
        assert status['total_files'] == 2
        assert status['status'] == "ready_for_incremental"
        
        print("\n🎉 All incremental download tests passed!")
        return True


def main():
    """Run incremental download tests."""
    print("Starting Incremental Download Tests...\n")
    
    try:
        if not test_incremental_downloads():
            print("❌ Incremental download tests failed")
            return 1
        
        print("\n" + "="*60)
        print("🎉 ALL INCREMENTAL TESTS PASSED! 🎉")
        print("The WBDG scraper incremental functionality is working correctly.")
        print("Features verified:")
        print("✓ Metadata tracking and persistence")
        print("✓ File change detection (size, last-modified)")
        print("✓ Incremental download (skip unchanged files)")
        print("✓ Status reporting")
        print("="*60)
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())