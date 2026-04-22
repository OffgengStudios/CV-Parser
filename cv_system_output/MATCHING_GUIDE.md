# Candidate Matching System

## Overview

This matching system helps you automatically rank candidates based on how well they fit a job description. It combines:

1. **Text Similarity** (TF-IDF + cosine similarity): How well the CV text matches the job description
2. **Skill Matching**: How many required skills from the job description are present in the CV

**Final Score** = (0.7 × text_similarity) + (0.3 × skill_match)

## Backend Changes

### 1. Database Model Update

Added `cv_text` field to the `Candidate` model to store the full extracted CV text:

```python
# database/models.py
class Candidate(Base):
    # ... existing fields ...
    cv_text: Mapped[str | None] = mapped_column(Text, nullable=True)
```

### 2. New Matching Module

Created `matching/matcher.py` with:
- `CandidateMatcher`: Class for batch matching
- `match_candidates()`: Convenience function
- `MatchResult`: Dataclass for results

### 3. Pipeline Update

The CV processing pipeline now stores the extracted `clean_text`:

```python
# api/pipeline.py
candidate = crud.create_candidate(
    db=db,
    # ... other fields ...
    cv_text=clean_text,  # NEW: Store full extracted text
    # ...
)
```

### 4. New API Endpoint

**POST** `/api/v1/match` — Match candidates against a job description

## API Endpoint

### Request

```json
{
  "job_description": "We are looking for a Python developer with Django experience...",
  "text_weight": 0.7,
  "skill_weight": 0.3,
  "limit": 10
}
```

**Parameters:**
- `job_description` (required): Job posting text (min 50 chars)
- `text_weight`: Weight for text similarity (0.0-1.0, default 0.7)
- `skill_weight`: Weight for skill matching (0.0-1.0, default 0.3)
- `limit`: Max results to return (1-100, default 10)

### Response

```json
{
  "total_candidates": 45,
  "matched_candidates": 10,
  "results": [
    {
      "candidate_id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "John Doe",
      "email": "john@example.com",
      "phone": "+1-555-0123",
      "skills": ["Python", "Django", "PostgreSQL", "Docker"],
      "category": "Information Technology (IT)",
      "subcategory": "Software Developer",
      "similarity_score": 0.87,
      "skill_match_score": 0.95,
      "final_score": 0.89,
      "matched_skills": ["Python", "Django", "PostgreSQL", "Docker", "Git"]
    }
    // ... more results ...
  ]
}
```

**Response Fields:**
- `total_candidates`: Total candidates in database
- `matched_candidates`: Candidates returned (limited by `limit`)
- `results`: Ranked list of candidates

Each result includes:
- `similarity_score`: Text matching score (0.0-1.0)
- `skill_match_score`: Percentage of required skills found (0.0-1.0)
- `final_score`: Combined score (0.0-1.0)
- `matched_skills`: Which job-required skills are in the CV

## Frontend Integration

### Option 1: React Component (Recommended)

Use the provided `JobMatcher.tsx` component:

```tsx
import JobMatcher from '@/components/JobMatcher';

export default function JobPage() {
  return <JobMatcher />;
}
```

Features:
- Paste job description
- Adjust text/skill weights
- Searchable results table
- Visual score bars
- Shows matched skills
- Responsive design

### Option 2: Vanilla JavaScript

Simple fetch example:

```javascript
async function matchCandidates(jobDescription) {
  try {
    const response = await fetch('http://127.0.0.1:8000/api/v1/match', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        job_description: jobDescription,
        text_weight: 0.7,
        skill_weight: 0.3,
        limit: 10,
      }),
    });

    if (!response.ok) {
      throw new Error('Matching failed');
    }

    const data = await response.json();
    console.log('Top match:', data.results[0]);
    return data.results;
  } catch (error) {
    console.error('Error:', error);
  }
}

// Usage
const jobDesc = `
We're looking for a Python developer with:
- 5+ years experience
- Django or FastAPI
- PostgreSQL
- Docker/Kubernetes
- AWS experience
`;

matchCandidates(jobDesc).then(results => {
  results.forEach((result, idx) => {
    console.log(`#${idx + 1}: ${result.name}`);
    console.log(`  Match: ${(result.final_score * 100).toFixed(0)}%`);
    console.log(`  Skills: ${result.matched_skills.join(', ')}`);
  });
});
```

### Option 3: HTML Form Example

```html
<!DOCTYPE html>
<html>
<head>
  <title>Job Matcher</title>
  <style>
    body { font-family: Arial; max-width: 1000px; margin: 0 auto; padding: 20px; }
    textarea { width: 100%; height: 150px; }
    table { width: 100%; border-collapse: collapse; margin-top: 20px; }
    th, td { border: 1px solid #ddd; padding: 10px; text-align: left; }
    th { background: #f5f5f5; }
    .score-high { color: green; font-weight: bold; }
    .score-low { color: orange; }
    .skill { display: inline-block; background: #e8f5e9; padding: 3px 8px; margin: 2px; border-radius: 3px; font-size: 12px; }
    button { padding: 10px 20px; background: #0066cc; color: white; border: none; border-radius: 4px; cursor: pointer; }
    button:hover { background: #0052a3; }
  </style>
</head>
<body>
  <h1>Job Matcher</h1>

  <textarea id="jobDesc" placeholder="Paste job description here..."></textarea>
  <br>
  <button onclick="matchCandidates()">Find Matches</button>
  <div id="loading" style="display: none;">Matching...</div>

  <table id="results" style="display: none;">
    <thead>
      <tr>
        <th>Name</th>
        <th>Category</th>
        <th>Match Score</th>
        <th>Skills</th>
        <th>Contact</th>
      </tr>
    </thead>
    <tbody id="resultsBody"></tbody>
  </table>
  <div id="error" style="color: red; margin-top: 10px;"></div>

  <script>
    async function matchCandidates() {
      const jobDesc = document.getElementById('jobDesc').value;
      const loading = document.getElementById('loading');
      const error = document.getElementById('error');
      const resultsTable = document.getElementById('results');

      if (jobDesc.length < 50) {
        error.textContent = 'Job description must be at least 50 characters';
        return;
      }

      loading.style.display = 'block';
      error.textContent = '';

      try {
        const response = await fetch('http://127.0.0.1:8000/api/v1/match', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            job_description: jobDesc,
            text_weight: 0.7,
            skill_weight: 0.3,
            limit: 20,
          }),
        });

        if (!response.ok) {
          throw new Error('Matching failed');
        }

        const data = await response.json();
        const tbody = document.getElementById('resultsBody');
        tbody.innerHTML = '';

        data.results.forEach(result => {
          const row = tbody.insertRow();
          row.innerHTML = `
            <td>${result.name || '(No name)'}</td>
            <td>${result.category || '—'}</td>
            <td class="score-${result.final_score > 0.7 ? 'high' : 'low'}">
              ${(result.final_score * 100).toFixed(0)}%
            </td>
            <td>
              ${result.matched_skills
                .slice(0, 3)
                .map(s => `<span class="skill">${s}</span>`)
                .join('')}
              ${result.matched_skills.length > 3 ? `<span class="skill">+${result.matched_skills.length - 3}</span>` : ''}
            </td>
            <td>${result.email || '—'}</td>
          `;
        });

        resultsTable.style.display = 'table';
        console.log(`Matched ${data.results.length} candidates out of ${data.total_candidates}`);
      } catch (err) {
        error.textContent = `Error: ${err.message}`;
      } finally {
        loading.style.display = 'none';
      }
    }
  </script>
</body>
</html>
```

## How It Works

### Matching Algorithm

1. **Extract Skills**: Parse job description to find required skills
2. **Calculate Text Similarity**: 
   - Vectorize job description and all CVs using TF-IDF
   - Calculate cosine similarity between job and each CV
3. **Calculate Skill Match**:
   - Extract skills from each CV
   - Count matches: `skill_score = matched_skills / required_skills`
4. **Combine Scores**:
   - `final_score = (0.7 × text_similarity) + (0.3 × skill_match)`
5. **Sort & Return**: Results ordered by final score (highest first)

### Supported Skills Database

The system recognizes 200+ skills across:
- Programming languages (Python, Java, TypeScript, etc.)
- Web frameworks (React, Django, FastAPI, etc.)
- Databases (PostgreSQL, MongoDB, etc.)
- Tools (Docker, Kubernetes, AWS, etc.)
- Office software (Excel, Salesforce, etc.)
- Languages and soft skills

To add more skills, edit `SKILLS_DATABASE` in `matching/matcher.py`.

## Performance Considerations

- **Time Complexity**: O(n × m) where n = candidates, m = job description length
- **Space**: Stores TF-IDF matrix in memory (~10KB per candidate)
- **Optimization**: For 1000+ candidates, consider:
  - Chunking: Process in batches
  - Pre-computing: Cache TF-IDF vectors
  - Filtering: Pre-filter by category before matching

## Troubleshooting

**"No results returned"**: 
- Check job description is > 50 characters
- Most candidates may have no matching skills

**"Score always 0.5"**:
- Few text overlaps between job and CVs
- Consider increasing skill_weight

**"API returns 500"**:
- Ensure scikit-learn is installed: `pip install scikit-learn`
- Check database has candidates with `cv_text` populated

## Next Steps

1. Run migration: `alembic upgrade head` (if using Alembic)
2. Upload CVs to populate database
3. Test via `/docs` (Swagger UI)
4. Integrate React component or custom frontend
5. Fine-tune `text_weight`/`skill_weight` based on results

---

## Files Modified

- `database/models.py` — Added `cv_text` field
- `api/pipeline.py` — Store `clean_text` to database
- `api/schemas.py` — Added matching request/response schemas
- `api/routes.py` — Added `/api/v1/match` endpoint

## Files Created

- `matching/matcher.py` — Matching engine
- `matching/__init__.py` — Package init
- `frontend/components/JobMatcher.tsx` — React component
