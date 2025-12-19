# Multi-Agent Development System

This directory contains agent instruction files for different specialized roles in the Dopetracks development process. Each agent has a specific expertise area and can be used to get focused, role-specific assistance.

## Available Agents

### 🎨 [product.md](./product.md) - Product Designer
**Role**: Challenge assumptions, clarify user intent, identify edge cases
**Use when**: Planning features, defining requirements, reviewing user flows
**Does NOT write code** - focuses on product thinking

### ⚙️ [backend.md](./backend.md) - Backend Developer
**Role**: FastAPI, Python, database, API implementation
**Use when**: Implementing endpoints, fixing backend bugs, optimizing queries
**Writes code** - Python/FastAPI expertise

### 🎨 [frontend.md](./frontend.md) - Frontend Developer
**Role**: JavaScript, HTML, CSS, user interface
**Use when**: Building UI, fixing frontend bugs, improving UX
**Writes code** - Frontend expertise

### 🗄️ [database.md](./database.md) - Database Architect
**Role**: SQLAlchemy, schema design, query optimization
**Use when**: Designing schemas, optimizing queries, planning migrations
**Writes code** - Database expertise

### 🔒 [security.md](./security.md) - Security Reviewer
**Role**: Authentication, authorization, security vulnerabilities
**Use when**: Reviewing security, implementing auth, handling sensitive data
**Writes code** - Security-focused

### 🌐 [api.md](./api.md) - API Designer
**Role**: RESTful API design, endpoint structure, documentation
**Use when**: Designing new endpoints, reviewing API consistency
**Writes code** - API design expertise

### 📊 [data_processing.md](./data_processing.md) - Data Processing Specialist
**Role**: iMessage parsing, Spotify integration, data pipelines
**Use when**: Processing messages, extracting Spotify links, optimizing data flow
**Writes code** - Data processing expertise

### 🚀 [devops.md](./devops.md) - DevOps Specialist
**Role**: Deployment, infrastructure, scaling, monitoring
**Use when**: Deploying to production, optimizing performance, setting up infrastructure
**Writes code** - Infrastructure expertise

## How to Use These Agents

### Method 1: Direct Reference in Chat
When asking for help, reference the agent file:

```
@agents/backend.md I need help implementing a new endpoint for user preferences
```

Or in Cursor:
```
Read agents/backend.md and help me implement a new endpoint
```

### Method 2: Copy-Paste Instructions
1. Open the relevant agent file
2. Copy the instructions
3. Paste at the start of your conversation with the AI
4. Then ask your question

### Method 3: Sequential Agent Review
For complex features, use multiple agents in sequence:

1. **Product** - Define requirements and edge cases
2. **API** - Design the endpoint structure
3. **Backend** - Implement the endpoint
4. **Database** - Review schema changes if needed
5. **Security** - Review for vulnerabilities
6. **Frontend** - Implement UI (if needed)
7. **DevOps** - Consider deployment implications

## Example Workflow

### Adding a New Feature: "Favorite Chats"

1. **Start with Product Agent**:
   ```
   Read agents/product.md
   I want to add a "favorite chats" feature. What edge cases should I consider?
   ```

2. **Design API with API Agent**:
   ```
   Read agents/api.md
   Design REST endpoints for favoriting/unfavoriting chats
   ```

3. **Review Database with Database Agent**:
   ```
   Read agents/database.md
   What schema changes are needed for favorite chats?
   ```

4. **Implement with Backend Agent**:
   ```
   Read agents/backend.md
   Implement the favorite chats endpoints
   ```

5. **Security Review**:
   ```
   Read agents/security.md
   Review this code for security issues: [paste code]
   ```

6. **Frontend Implementation**:
   ```
   Read agents/frontend.md
   Add UI for favoriting chats
   ```

## Best Practices

1. **Start with Product** - Always clarify requirements first
2. **Security Early** - Review security implications before implementation
3. **Database First** - Design schema before writing queries
4. **API Consistency** - Follow existing patterns
5. **End-to-End** - Use multiple agents to ensure completeness

## Agent Collaboration

Agents can work together:
- **Product + API** - Define requirements and design endpoints
- **Backend + Database** - Implement features with proper queries
- **Security + Backend** - Secure implementation review
- **Frontend + API** - Ensure UI matches API design
- **DevOps + All** - Production readiness review

## Tips

- **Be specific**: Tell the agent which file/feature you're working on
- **Provide context**: Share relevant code or error messages
- **Iterate**: Use multiple agents to refine your solution
- **Document**: Update documentation as you work with agents

## Customization

Feel free to modify agent instructions to match your preferences:
- Add project-specific patterns
- Include your coding style preferences
- Add references to specific files or patterns
- Customize for your team's workflow

---

**Remember**: These agents are tools to help you think through problems from different perspectives. Use them to get specialized, focused assistance for each aspect of your application.

