<!-- Template Version: 1.1.0 -->
# LOCAL_DEV.md

> **TEMPLATE_INTENT:** Complete local development setup guide. Get a new developer running quickly.

> Last updated: YYYY-MM-DD
> Updated by: [Human/Claude]

---

## Prerequisites

<!-- FILL: What needs to be installed before setup -->

| Requirement | Version | Installation |
|-------------|---------|--------------|
| [Language runtime] | [version] | [install command or link] |
| [Package manager] | [version] | [install command or link] |
| [Database] | [version] | [install command or link] |
| [Other tools] | [version] | [install command or link] |

### Optional but Recommended

- [Tool]: [Why it's helpful]
- [Tool]: [Why it's helpful]

---

## Quick Start

<!-- FILL: Fastest path to a running local environment -->

```bash
# 1. Clone the repository
git clone [repo-url]
cd [project-name]

# 2. Install dependencies
[command]

# 3. Set up environment
[command]

# 4. Start the application
[command]
```

After these steps, the application should be available at: `[local URL]`

---

## Detailed Setup

### 1. Environment Configuration

```bash
# Copy example environment file
cp .env.example .env
```

**Required environment variables to set:**

| Variable | How to Get It |
|----------|---------------|
| `[VAR_NAME]` | [Instructions to obtain this value] |

**Optional variables:**

| Variable | Default | Purpose |
|----------|---------|---------|
| `[VAR_NAME]` | `[default]` | [What it does] |

### 2. Database Setup

<!-- FILL: How to set up local database. Delete if no database -->

```bash
# Start database (if using Docker)
[command]

# Or connect to local installation
[instructions]

# Run migrations
[command]

# Seed with test data (optional)
[command]
```

### 3. Install Dependencies

```bash
# [Language/framework specific commands]
[command]
```

### 4. Start the Application

```bash
# Start all services
[command]

# Or start individually:
# [Service 1]
[command]

# [Service 2]
[command]
```

---

## Running with Docker

<!-- FILL: Docker-based setup. Delete if not using Docker -->

```bash
# Build and start all services
docker-compose up --build

# Start in background
docker-compose up -d

# View logs
docker-compose logs -f [service-name]

# Stop everything
docker-compose down
```

### Docker Services

| Service | Port | Description |
|---------|------|-------------|
| [service] | [port] | [what it is] |

---

## Mocking External Services

<!-- FILL: How to work without real external dependencies -->

### [External Service Name]

**Option 1: Use test/sandbox environment**
```
[Environment variables or configuration for sandbox]
```

**Option 2: Mock locally**
```bash
[How to run a local mock]
```

**Option 3: Skip in development**
```
[Configuration to disable this integration locally]
```

---

## Test Data

<!-- FILL: How to get useful data for local development -->

### Seed Data

```bash
# Load standard development fixtures
[command]

# Create specific test scenarios
[command]
```

### Test Accounts

| Account | Credentials | Purpose |
|---------|-------------|---------|
| [type] | [username/password or how to create] | [what to test with it] |

---

## Common Local Development Tasks

### Reset Database

```bash
# Drop and recreate
[command]

# Or just reseed
[command]
```

### Clear Caches

```bash
[command]
```

### Run Tests

```bash
# All tests
[command]

# Specific test file
[command]

# With coverage
[command]
```

### Linting / Formatting

```bash
# Check for issues
[command]

# Auto-fix
[command]
```

---

## Troubleshooting Local Setup

### [Common Problem 1]

**Symptom:** [What you see]

**Cause:** [Why it happens]

**Fix:**
```bash
[commands to fix]
```

---

### [Common Problem 2]

**Symptom:** [What you see]

**Fix:**
```bash
[commands to fix]
```

---

## IDE Setup

<!-- FILL: Recommended IDE configuration. Delete or customize -->

### VS Code

Recommended extensions:
- [Extension name] - [Why]

Workspace settings (`.vscode/settings.json`):
```json
{
  // [Recommended settings]
}
```

### [Other IDE]

[Setup instructions]

---

## Useful Local Commands

<!-- FILL: Commands developers frequently need -->

```bash
# [Description]
[command]

# [Description]
[command]

# [Description]
[command]
```
