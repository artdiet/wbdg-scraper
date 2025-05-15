# Cursor IDE Setup and Usage

**Project Refactoring Note:**
- This project was refactored and modernized using Cursor on 15 May 2025. The refactor included improved error handling, robust documentation, and the addition of automated unit tests and build checks in Palantir Foundry.

## IDE Configuration

### Recommended Settings

1. **Editor Settings**
   - Tab size: 4 spaces
   - Line wrapping: enabled
   - Auto-save: enabled
   - File encoding: UTF-8

2. **Language Support**
   - Python
   - Java
   - Gradle
   - YAML
   - JSON
   - Foundry Transform DSL

### Useful Shortcuts

1. **Navigation**
   - `Ctrl+P`: Quick file open
   - `Ctrl+Shift+P`: Command palette
   - `Ctrl+G`: Go to line
   - `Ctrl+Shift+O`: Go to symbol

2. **Editing**
   - `Ctrl+/`: Toggle comment
   - `Alt+Up/Down`: Move line up/down
   - `Ctrl+D`: Select next occurrence
   - `Ctrl+Shift+L`: Select all occurrences

3. **Search**
   - `Ctrl+F`: Find in file
   - `Ctrl+Shift+F`: Find in project
   - `Ctrl+H`: Replace in file

## Project-Specific Setup for Palantir Foundry

### Working with Foundry

- **Builds and Testing:**
  - All code and dependency changes must be built and tested within the Foundry platform. Local testing is limited; always validate your changes by triggering a build in Foundry.
  - Build times can be significant (10–20 minutes for full dependency resolution and environment setup).
  - Use the "Test" and "Preview" features in Foundry to validate transforms. These features run your code in the actual Foundry environment, ensuring all dependencies and integrations are correct.
  - If you add or update dependencies (e.g., `pypdf2`, `tqdm`, `tenacity`), update `meta.yml` or use the Foundry package installer. Wait for the environment to rebuild before running your code.

- **Dependency Management:**
  - Use the `meta.yml` file in `transforms-python/conda_recipe/` to manage Python dependencies. The package names must match Conda's naming (e.g., `pypdf2` not `PyPDF2`).
  - After adding dependencies, commit and push changes, then trigger a new build in Foundry.

- **Testing in Foundry:**
  - Foundry supports transform-level tests. Place test scripts in your repo and use the platform's test runner.
  - You can mock external systems or point to specific URLs for controlled tests.
  - Always verify that your tests pass in Foundry, as the environment may differ from local setups.
  - Automated unit tests are now part of the workflow and will run during build checks.

- **AIP Assist:**
  - Foundry's AI assistant (AIP Assist) can read project files, including this outline, to provide context-aware suggestions and code reviews.
  - Keep documentation up to date and clear to help AIP Assist and human reviewers understand project structure and best practices.

- **Troubleshooting:**
  - If you see `ModuleNotFoundError`, ensure the package is in `meta.yml` and the environment has rebuilt.
  - For long build times, check the build logs for dependency resolution and caching status.
  - Use the crawl log and error logs for debugging transform execution issues.

### Python Environment

1. **Virtual Environment (for local linting only)**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   pip install -r requirements.txt
   ```
   > Note: Actual execution and dependency resolution happen in Foundry.

### Java/Gradle Setup

1. **JDK Configuration**
   - Set JAVA_HOME environment variable
   - Configure Gradle JDK in IDE settings
   - Configure Foundry SDK

2. **Gradle Tasks**
   - `./gradlew build`: Build project
   - `./gradlew test`: Run tests
   - `./gradlew clean`: Clean build
   - `./gradlew foundryDeploy`: Deploy to Foundry

### Foundry Setup

1. **CLI Configuration**
   ```bash
   foundry-cli configure
   foundry-cli login
   ```

2. **Transform Development**
   - Use Foundry Transform SDK
   - Configure transform parameters
   - Test transforms locally (limited) and in Foundry (recommended)

## Debugging

1. **Python Debugging**
   - Set breakpoints with F9
   - Start debug session with F5
   - Step through code with F10/F11
   - Debug Foundry transforms using platform logs and crawl logs

2. **Java Debugging**
   - Configure run configurations
   - Use debug perspective
   - Monitor variables and call stack
   - Debug Foundry SDK

## Version Control

1. **Git Integration**
   - Stage changes: `Ctrl+Shift+G`
   - Commit: `Ctrl+Enter`
   - Push/Pull: Use Git panel

2. **Branch Management**
   - Create branch: `git checkout -b feature/name`
   - Switch branch: `git checkout branch-name`
   - Merge: Use Git panel or command line

## Code Quality

1. **Linting**
   - Python: flake8, pylint
   - Java: CheckStyle, PMD
   - Foundry: Transform validation

2. **Formatting**
   - Python: black
   - Java: Google Java Format
   - Foundry: Transform formatting

## Performance Tips

1. **Memory Management**
   - Monitor memory usage
   - Clear caches when needed
   - Close unused files
   - Optimize Foundry resources

2. **Search Optimization**
   - Use specific file patterns
   - Exclude build directories
   - Use advanced search options
   - Filter Foundry datasets 