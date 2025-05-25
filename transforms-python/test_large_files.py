#!/usr/bin/env python3
"""
Testing script for WBDG scraper with large file handling capabilities.

This script tests the scraper's ability to handle:
- Large numbers of files (simulating ~700 PDFs)
- Various file sizes including large files
- Rate limiting and timeout handling
- Memory management during downloads
- Error recovery and retries

Usage:
    python test_large_files.py [--mock] [--concurrent] [--output-dir DIR]
"""

import argparse
import json
import time
import random
import hashlib
import tempfile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Tuple
import threading

import responses
from myproject.datasets.wbdg_scraper import WBDGScraper


class LargeFileTestHarness:
    """Test harness for simulating large-scale scraping scenarios."""
    
    def __init__(self, output_dir: str, use_mock: bool = True):
        """Initialize test harness.
        
        Parameters
        ----------
        output_dir : str
            Directory for test outputs
        use_mock : bool
            Whether to use mock HTTP responses or real network
        """
        self.output_dir = Path(output_dir)
        self.use_mock = use_mock
        self.test_files: List[Dict] = []
        
        # Create test directory structure
        self.test_data_dir = self.output_dir / "test_data"
        self.results_dir = self.output_dir / "results"
        self.test_data_dir.mkdir(parents=True, exist_ok=True)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        
        # Performance tracking
        self.start_time = None
        self.metrics = {
            "files_generated": 0,
            "downloads_attempted": 0,
            "downloads_successful": 0,
            "downloads_failed": 0,
            "total_bytes": 0,
            "max_memory_usage": 0
        }
    
    def generate_test_files(self, count: int = 700) -> List[Dict]:
        """Generate metadata for test PDF files.
        
        Parameters
        ----------
        count : int
            Number of test files to generate
            
        Returns
        -------
        List[Dict]
            List of file metadata dictionaries
        """
        print(f"Generating metadata for {count} test files...")
        
        file_sizes = [
            (1, 100),        # Small files: 1-100 KB (70%)
            (100, 1000),     # Medium files: 100KB-1MB (20%)
            (1000, 10000),   # Large files: 1-10MB (8%)
            (10000, 50000)   # Very large files: 10-50MB (2%)
        ]
        
        size_weights = [0.7, 0.2, 0.08, 0.02]
        
        categories = [
            "structural", "mechanical", "electrical", "fire-protection",
            "environmental", "security", "telecommunications", "civil"
        ]
        
        for i in range(count):
            # Select file size category
            size_category = random.choices(file_sizes, weights=size_weights)[0]
            size_kb = random.randint(size_category[0], size_category[1])
            size_bytes = size_kb * 1024
            
            # Generate file metadata
            category = random.choice(categories)
            file_num = f"{i+1:03d}"
            
            file_info = {
                "filename": f"UFC-{random.randint(1,9)}-{random.randint(100,999)}-{file_num}.pdf",
                "url": f"https://test.wbdg.org/dod/ufc/{category}/UFC-{random.randint(1,9)}-{random.randint(100,999)}-{file_num}.pdf",
                "size_bytes": size_bytes,
                "category": category,
                "download_delay": random.uniform(0.1, 2.0),  # Simulate variable server response
                "should_fail": random.random() < 0.05,  # 5% failure rate
                "content_hash": hashlib.md5(f"content_{i}".encode()).hexdigest()
            }
            
            self.test_files.append(file_info)
            
        self.metrics["files_generated"] = len(self.test_files)
        print(f"Generated {len(self.test_files)} test files")
        
        # Save test manifest
        manifest_path = self.test_data_dir / "test_manifest.json"
        with open(manifest_path, 'w') as f:
            json.dump(self.test_files, f, indent=2)
            
        return self.test_files
    
    def setup_mock_responses(self):
        """Setup mock HTTP responses for testing."""
        if not self.use_mock:
            return
            
        print("Setting up mock HTTP responses...")
        
        # Mock root page with links to all test files
        root_html = self._generate_root_html()
        responses.add(
            responses.GET,
            "https://test.wbdg.org/dod/ufc",
            body=root_html,
            status=200
        )
        
        # Mock category pages
        for category in set(file_info["category"] for file_info in self.test_files):
            category_html = self._generate_category_html(category)
            responses.add(
                responses.GET,
                f"https://test.wbdg.org/dod/ufc/{category}/",
                body=category_html,
                status=200
            )
        
        # Mock PDF file responses
        for file_info in self.test_files:
            self._setup_file_response(file_info)
    
    def _generate_root_html(self) -> str:
        """Generate HTML for root page with category links."""
        categories = set(file_info["category"] for file_info in self.test_files)
        
        links = []
        for category in categories:
            links.append(f'<li><a href="{category}/">{category.title()}</a></li>')
        
        return f"""
        <!DOCTYPE html>
        <html>
        <head><title>UFC Directory - Test</title></head>
        <body>
            <h1>Unified Facilities Criteria - Test Environment</h1>
            <ul>
                {''.join(links)}
            </ul>
        </body>
        </html>
        """
    
    def _generate_category_html(self, category: str) -> str:
        """Generate HTML for category page with PDF links."""
        category_files = [f for f in self.test_files if f["category"] == category]
        
        links = []
        for file_info in category_files:
            links.append(f'<li><a href="../{file_info["filename"]}">{file_info["filename"]}</a></li>')
        
        return f"""
        <!DOCTYPE html>
        <html>
        <head><title>{category.title()} - UFC</title></head>
        <body>
            <h1>{category.title()} Criteria</h1>
            <ul>
                {''.join(links)}
            </ul>
        </body>
        </html>
        """
    
    def _setup_file_response(self, file_info: Dict):
        """Setup mock response for a single file."""
        url = file_info["url"]
        
        if file_info["should_fail"]:
            # Simulate server errors
            responses.add(
                responses.HEAD,
                url,
                status=random.choice([404, 500, 503])
            )
            responses.add(
                responses.GET,
                url,
                status=random.choice([404, 500, 503])
            )
        else:
            # Generate fake PDF content
            content = self._generate_fake_pdf_content(file_info)
            
            # HEAD response for size check
            responses.add(
                responses.HEAD,
                url,
                headers={"content-length": str(len(content))},
                status=200
            )
            
            # GET response with potential delay
            def delayed_response(request):
                time.sleep(file_info["download_delay"])
                return (200, {}, content)
            
            responses.add_callback(
                responses.GET,
                url,
                callback=delayed_response
            )
    
    def _generate_fake_pdf_content(self, file_info: Dict) -> bytes:
        """Generate fake PDF content of specified size."""
        # Minimal PDF header
        content = b"%PDF-1.4\n"
        content += f"% {file_info['filename']}\n".encode()
        content += f"% Hash: {file_info['content_hash']}\n".encode()
        
        # Pad to desired size
        current_size = len(content)
        target_size = file_info["size_bytes"]
        
        if target_size > current_size:
            padding_size = target_size - current_size - 10  # Leave room for EOF
            padding = b"x" * padding_size
            content += padding
        
        content += b"\n%%EOF"
        return content
    
    def run_performance_test(self, scraper: WBDGScraper) -> Dict:
        """Run performance test with the scraper.
        
        Parameters
        ----------
        scraper : WBDGScraper
            Configured scraper instance
            
        Returns
        -------
        Dict
            Performance test results
        """
        print("Starting performance test...")
        self.start_time = time.time()
        
        # Override scraper's delay for faster testing
        original_delay = scraper.REQUEST_DELAY_S
        scraper.REQUEST_DELAY_S = 0.01  # Minimal delay for testing
        
        try:
            # Run the scraper
            summary = scraper.run_full_scrape()
            
            # Calculate performance metrics
            end_time = time.time()
            duration = end_time - self.start_time
            
            # Analyze results
            results = {
                "test_config": {
                    "total_files": len(self.test_files),
                    "expected_failures": sum(1 for f in self.test_files if f["should_fail"]),
                    "use_mock": self.use_mock
                },
                "performance": {
                    "duration_seconds": duration,
                    "files_per_second": len(self.test_files) / duration if duration > 0 else 0,
                    "total_size_mb": sum(f["size_bytes"] for f in self.test_files) / (1024 * 1024)
                },
                "scraper_results": summary,
                "detailed_metrics": self.metrics
            }
            
            # Save results
            results_file = self.results_dir / f"performance_test_{int(time.time())}.json"
            with open(results_file, 'w') as f:
                json.dump(results, f, indent=2)
            
            print(f"Performance test completed in {duration:.1f}s")
            print(f"Files processed: {summary.get('success_count', 0)}/{len(self.test_files)}")
            print(f"Results saved to: {results_file}")
            
            return results
            
        finally:
            # Restore original delay
            scraper.REQUEST_DELAY_S = original_delay
    
    def run_stress_test(self, scraper: WBDGScraper, max_workers: int = 5) -> Dict:
        """Run stress test with concurrent downloads.
        
        Parameters
        ----------
        scraper : WBDGScraper
            Configured scraper instance
        max_workers : int
            Maximum concurrent download threads
            
        Returns
        -------
        Dict
            Stress test results
        """
        print(f"Starting stress test with {max_workers} concurrent workers...")
        self.start_time = time.time()
        
        # Get PDF URLs from test files
        pdf_urls = {f["url"] for f in self.test_files if not f["should_fail"]}
        
        results = {}
        lock = threading.Lock()
        
        def download_single_pdf(url: str) -> Tuple[str, str]:
            """Download a single PDF and return result."""
            try:
                # Simulate individual download
                filename = Path(url).name
                result = scraper.download_pdfs({url})
                return filename, result.get(filename, "unknown")
            except Exception as e:
                return Path(url).name, f"error: {str(e)}"
        
        # Run concurrent downloads
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_url = {
                executor.submit(download_single_pdf, url): url 
                for url in list(pdf_urls)[:50]  # Limit for testing
            }
            
            for future in as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    filename, status = future.result()
                    with lock:
                        results[filename] = status
                except Exception as e:
                    with lock:
                        results[Path(url).name] = f"future_error: {str(e)}"
        
        end_time = time.time()
        duration = end_time - self.start_time
        
        stress_results = {
            "test_config": {
                "max_workers": max_workers,
                "files_tested": len(results),
                "use_mock": self.use_mock
            },
            "performance": {
                "duration_seconds": duration,
                "files_per_second": len(results) / duration if duration > 0 else 0
            },
            "results": results,
            "success_rate": sum(1 for status in results.values() if status == "success") / len(results)
        }
        
        # Save results
        results_file = self.results_dir / f"stress_test_{int(time.time())}.json"
        with open(results_file, 'w') as f:
            json.dump(stress_results, f, indent=2)
        
        print(f"Stress test completed in {duration:.1f}s")
        print(f"Success rate: {stress_results['success_rate']:.1%}")
        print(f"Results saved to: {results_file}")
        
        return stress_results


def main():
    """Main entry point for large file testing."""
    parser = argparse.ArgumentParser(description="WBDG Scraper Large File Test")
    parser.add_argument("--mock", action="store_true", default=True,
                       help="Use mock HTTP responses (default)")
    parser.add_argument("--real", action="store_true",
                       help="Use real network requests (overrides --mock)")
    parser.add_argument("--output-dir", default="test_output",
                       help="Output directory for test results")
    parser.add_argument("--file-count", type=int, default=700,
                       help="Number of test files to simulate")
    parser.add_argument("--concurrent", action="store_true",
                       help="Run stress test with concurrent downloads")
    parser.add_argument("--max-workers", type=int, default=5,
                       help="Maximum concurrent workers for stress test")
    
    args = parser.parse_args()
    
    # Determine mock usage
    use_mock = args.mock and not args.real
    
    print("=== WBDG Scraper Large File Test ===")
    print(f"Test mode: {'Mock' if use_mock else 'Real network'}")
    print(f"File count: {args.file_count}")
    print(f"Output directory: {args.output_dir}")
    
    # Setup test harness
    harness = LargeFileTestHarness(args.output_dir, use_mock)
    
    # Generate test files
    test_files = harness.generate_test_files(args.file_count)
    
    # Setup scraper
    scraper = WBDGScraper(
        base_url="https://test.wbdg.org/" if use_mock else "https://www.wbdg.org/",
        output_dir=str(harness.results_dir / "scraper_output"),
        log_level="INFO"
    )
    
    if use_mock:
        # Setup mock responses
        harness.setup_mock_responses()
        
        # Run with mocked responses
        responses.start()
        try:
            if args.concurrent:
                results = harness.run_stress_test(scraper, args.max_workers)
            else:
                results = harness.run_performance_test(scraper)
        finally:
            responses.stop()
            responses.reset()
    else:
        # Run with real network (only performance test for safety)
        print("WARNING: Running with real network requests")
        print("This will actually download files from WBDG!")
        
        confirm = input("Continue? (y/N): ")
        if confirm.lower() != 'y':
            print("Test cancelled")
            return
            
        results = harness.run_performance_test(scraper)
    
    # Print summary
    print("\n=== Test Summary ===")
    if "performance" in results:
        perf = results["performance"]
        print(f"Duration: {perf['duration_seconds']:.1f}s")
        print(f"Rate: {perf['files_per_second']:.1f} files/second")
        if "total_size_mb" in perf:
            print(f"Total size: {perf['total_size_mb']:.1f} MB")
    
    if "scraper_results" in results:
        scraper_results = results["scraper_results"]
        print(f"Success rate: {scraper_results.get('success_count', 0)}/{scraper_results.get('pdfs_found', 0)}")
    
    print(f"Results saved to: {harness.results_dir}")


if __name__ == "__main__":
    main()