"""
Unit tests for WBDG scraper functionality.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
import pytest
import responses
from bs4 import BeautifulSoup

from myproject.datasets.wbdg_scraper import WBDGScraper


class TestWBDGScraper:
    """Test suite for WBDGScraper class."""
    
    def setup_method(self):
        """Setup test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.scraper = WBDGScraper(
            base_url="https://test.wbdg.org/",
            output_dir=self.temp_dir,
            log_level="DEBUG"
        )
    
    def test_init(self):
        """Test scraper initialization."""
        assert self.scraper.base_url == "https://test.wbdg.org/"
        assert self.scraper.output_dir == Path(self.temp_dir)
        assert self.scraper.pdfs_dir.exists()
        assert self.scraper.logs_dir.exists()
        assert self.scraper.INDEX_ROOT == "dod/ufc"
        assert self.scraper.REQUEST_DELAY_S == 0.25
        assert self.scraper.MAX_RETRIES == 3
    
    @responses.activate
    def test_crawl_for_pdfs_simple(self):
        """Test basic PDF crawling."""
        # Mock the root page
        root_html = """
        <html>
            <body>
                <a href="document1.pdf">Document 1</a>
                <a href="subpage.html">Subpage</a>
                <a href="external.pdf">External PDF</a>
            </body>
        </html>
        """
        
        # Mock subpage
        subpage_html = """
        <html>
            <body>
                <a href="document2.pdf">Document 2</a>
                <a href="https://external.com/doc.pdf">External</a>
            </body>
        </html>
        """
        
        responses.add(
            responses.GET,
            "https://test.wbdg.org/dod/ufc",
            body=root_html,
            status=200
        )
        
        responses.add(
            responses.GET,
            "https://test.wbdg.org/dod/subpage.html",
            body=subpage_html,
            status=200
        )
        
        pdf_urls = self.scraper.crawl_for_pdfs()
        
        expected_pdfs = {
            "https://test.wbdg.org/dod/document1.pdf",
            "https://test.wbdg.org/dod/external.pdf"
        }
        
        assert pdf_urls == expected_pdfs
        assert len(self.scraper.visited_pages) == 2
        assert len(self.scraper.log_entries) >= 2  # At least success logs
    
    @responses.activate
    def test_crawl_handles_errors(self):
        """Test crawling handles HTTP errors gracefully."""
        responses.add(
            responses.GET,
            "https://test.wbdg.org/dod/ufc",
            status=404
        )
        
        pdf_urls = self.scraper.crawl_for_pdfs()
        
        assert len(pdf_urls) == 0
        # Should have error log entry
        error_logs = [log for log in self.scraper.log_entries 
                     if log.get("event_type") == "crawl_error"]
        assert len(error_logs) >= 1
    
    def test_validate_pdf_valid(self):
        """Test PDF validation with valid PDF content."""
        # Create a minimal valid PDF
        valid_pdf = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n"
        valid_pdf += b"2 0 obj\n<<\n/Type /Pages\n/Kids [3 0 R]\n/Count 1\n>>\nendobj\n"
        valid_pdf += b"3 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n>>\nendobj\n"
        valid_pdf += b"xref\n0 4\n0000000000 65535 f\n"
        valid_pdf += b"0000000009 00000 n\n0000000074 00000 n\n0000000153 00000 n\n"
        valid_pdf += b"trailer\n<<\n/Size 4\n/Root 1 0 R\n>>\nstartxref\n208\n%%EOF"
        
        # Mock PdfReader to avoid complex PDF creation
        with patch('myproject.datasets.wbdg_scraper.PdfReader') as mock_reader:
            mock_reader.return_value = Mock()
            result = self.scraper._validate_pdf(valid_pdf)
            assert result is True
    
    def test_validate_pdf_invalid(self):
        """Test PDF validation with invalid content."""
        invalid_content = b"This is not a PDF file"
        
        with patch('myproject.datasets.wbdg_scraper.PdfReader') as mock_reader:
            mock_reader.side_effect = Exception("Invalid PDF")
            result = self.scraper._validate_pdf(invalid_content)
            assert result is False
    
    @responses.activate
    def test_download_pdfs_success(self):
        """Test successful PDF download."""
        pdf_content = b"%PDF-1.4\ntest content"
        
        responses.add(
            responses.HEAD,
            "https://test.wbdg.org/test.pdf",
            headers={"content-length": str(len(pdf_content))},
            status=200
        )
        
        responses.add(
            responses.GET,
            "https://test.wbdg.org/test.pdf",
            body=pdf_content,
            status=200
        )
        
        with patch.object(self.scraper, '_validate_pdf', return_value=True):
            pdf_urls = {"https://test.wbdg.org/test.pdf"}
            results = self.scraper.download_pdfs(pdf_urls)
            
            assert results["test.pdf"] == "success"
            
            # Check file was created
            output_file = self.scraper.pdfs_dir / "test.pdf"
            assert output_file.exists()
            assert output_file.read_bytes() == pdf_content
    
    @responses.activate
    def test_download_pdfs_too_large(self):
        """Test download rejection for oversized files."""
        large_size = self.scraper.MAX_FILE_SIZE + 1
        
        responses.add(
            responses.HEAD,
            "https://test.wbdg.org/large.pdf",
            headers={"content-length": str(large_size)},
            status=200
        )
        
        pdf_urls = {"https://test.wbdg.org/large.pdf"}
        results = self.scraper.download_pdfs(pdf_urls)
        
        assert results["large.pdf"] == "too_large"
        
        # Check file was not created
        output_file = self.scraper.pdfs_dir / "large.pdf"
        assert not output_file.exists()
    
    @responses.activate
    def test_download_pdfs_invalid_format(self):
        """Test download rejection for invalid PDF format."""
        fake_pdf = b"This is not a PDF"
        
        responses.add(
            responses.HEAD,
            "https://test.wbdg.org/fake.pdf",
            headers={"content-length": str(len(fake_pdf))},
            status=200
        )
        
        responses.add(
            responses.GET,
            "https://test.wbdg.org/fake.pdf",
            body=fake_pdf,
            status=200
        )
        
        with patch.object(self.scraper, '_validate_pdf', return_value=False):
            pdf_urls = {"https://test.wbdg.org/fake.pdf"}
            results = self.scraper.download_pdfs(pdf_urls)
            
            assert results["fake.pdf"] == "invalid_pdf"
            
            # Check file was not created
            output_file = self.scraper.pdfs_dir / "fake.pdf"
            assert not output_file.exists()
    
    def test_download_pdfs_skip_existing(self):
        """Test skipping existing files."""
        # Create existing file
        existing_file = self.scraper.pdfs_dir / "existing.pdf"
        existing_file.write_bytes(b"existing content")
        
        pdf_urls = {"https://test.wbdg.org/existing.pdf"}
        results = self.scraper.download_pdfs(pdf_urls)
        
        assert results["existing.pdf"] == "skipped"
    
    def test_log_event(self):
        """Test event logging functionality."""
        self.scraper._log_event("test_event", {"key": "value"})
        
        assert len(self.scraper.log_entries) == 1
        entry = self.scraper.log_entries[0]
        assert entry["event_type"] == "test_event"
        assert entry["key"] == "value"
        assert "timestamp" in entry
    
    def test_save_crawl_log(self):
        """Test saving crawl log to file."""
        # Add some log entries
        self.scraper._log_event("test1", {"data": "value1"})
        self.scraper._log_event("test2", {"data": "value2"})
        
        self.scraper.save_crawl_log()
        
        log_file = self.scraper.logs_dir / "crawl_log.json"
        assert log_file.exists()
        
        with open(log_file) as f:
            saved_logs = json.load(f)
            
        assert len(saved_logs) == 2
        assert saved_logs[0]["event_type"] == "test1"
        assert saved_logs[1]["event_type"] == "test2"
    
    @responses.activate
    def test_run_full_scrape(self):
        """Test complete scraping workflow."""
        # Mock crawl response
        html_content = """
        <html>
            <body>
                <a href="test1.pdf">Test PDF 1</a>
                <a href="test2.pdf">Test PDF 2</a>
            </body>
        </html>
        """
        
        responses.add(
            responses.GET,
            "https://test.wbdg.org/dod/ufc",
            body=html_content,
            status=200
        )
        
        # Mock PDF downloads
        for i in [1, 2]:
            pdf_content = f"%PDF-1.4\ntest content {i}".encode()
            
            responses.add(
                responses.HEAD,
                f"https://test.wbdg.org/dod/test{i}.pdf",
                headers={"content-length": str(len(pdf_content))},
                status=200
            )
            
            responses.add(
                responses.GET,
                f"https://test.wbdg.org/dod/test{i}.pdf",
                body=pdf_content,
                status=200
            )
        
        with patch.object(self.scraper, '_validate_pdf', return_value=True):
            summary = self.scraper.run_full_scrape()
            
        assert summary["pages_visited"] == 1
        assert summary["pdfs_found"] == 2
        assert summary["success_count"] == 2
        assert "duration_seconds" in summary
        
        # Check files were created
        assert (self.scraper.pdfs_dir / "test1.pdf").exists()
        assert (self.scraper.pdfs_dir / "test2.pdf").exists()
        assert (self.scraper.logs_dir / "crawl_log.json").exists()


class TestWBDGScraperIntegration:
    """Integration tests for scraper functionality."""
    
    def setup_method(self):
        """Setup test environment."""
        self.temp_dir = tempfile.mkdtemp()
    
    @responses.activate
    def test_real_world_scenario(self):
        """Test scraper with realistic HTML structure."""
        # Create a more realistic WBDG page structure
        root_html = """
        <!DOCTYPE html>
        <html>
        <head><title>UFC Directory</title></head>
        <body>
            <div class="content">
                <h1>Unified Facilities Criteria</h1>
                <ul>
                    <li><a href="categories/structural/">Structural</a></li>
                    <li><a href="categories/mechanical/">Mechanical</a></li>
                    <li><a href="UFC-1-200-01.pdf">UFC 1-200-01 Design Guide</a></li>
                    <li><a href="UFC-3-230-01.pdf">UFC 3-230-01 Water Storage</a></li>
                </ul>
            </div>
        </body>
        </html>
        """
        
        structural_html = """
        <!DOCTYPE html>
        <html>
        <body>
            <h2>Structural Criteria</h2>
            <ul>
                <li><a href="../UFC-3-301-01.pdf">UFC 3-301-01 Structural Design</a></li>
                <li><a href="../UFC-3-310-01.pdf">UFC 3-310-01 Seismic Design</a></li>
            </ul>
        </body>
        </html>
        """
        
        # Mock responses
        responses.add(
            responses.GET,
            "https://test.wbdg.org/dod/ufc",
            body=root_html,
            status=200
        )
        
        responses.add(
            responses.GET,
            "https://test.wbdg.org/dod/ufc/categories/structural/",
            body=structural_html,
            status=200
        )
        
        # Mock PDF files
        pdf_files = [
            "UFC-1-200-01.pdf",
            "UFC-3-230-01.pdf", 
            "UFC-3-301-01.pdf",
            "UFC-3-310-01.pdf"
        ]
        
        for pdf_file in pdf_files:
            pdf_content = f"%PDF-1.4\n{pdf_file} content".encode()
            
            # HEAD request for size check
            responses.add(
                responses.HEAD,
                f"https://test.wbdg.org/dod/ufc/{pdf_file}",
                headers={"content-length": str(len(pdf_content))},
                status=200
            )
            
            # GET request for download
            responses.add(
                responses.GET,
                f"https://test.wbdg.org/dod/ufc/{pdf_file}",
                body=pdf_content,
                status=200
            )
        
        scraper = WBDGScraper(
            base_url="https://test.wbdg.org/",
            output_dir=self.temp_dir,
            log_level="INFO"
        )
        
        with patch.object(scraper, '_validate_pdf', return_value=True):
            summary = scraper.run_full_scrape()
        
        # Verify results
        assert summary["pages_visited"] == 2  # Root + structural page
        assert summary["pdfs_found"] == 4
        assert summary["success_count"] == 4
        
        # Verify all PDFs were downloaded
        for pdf_file in pdf_files:
            pdf_path = scraper.pdfs_dir / pdf_file
            assert pdf_path.exists()
            content = pdf_path.read_bytes()
            assert pdf_file.encode() in content