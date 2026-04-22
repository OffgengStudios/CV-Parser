/**
 * components/JobMatcher.tsx — Job description matching interface
 *
 * Features:
 * - Paste job description
 * - Configure matching weights
 * - Display ranked results in searchable table
 * - Show matched skills and scores
 */

import React, { useState } from 'react';

interface MatchedCandidate {
  candidate_id: string;
  name: string | null;
  email: string | null;
  phone: string | null;
  skills: string[];
  category: string | null;
  subcategory: string | null;
  similarity_score: number;
  skill_match_score: number;
  final_score: number;
  matched_skills: string[];
}

interface MatchResponse {
  total_candidates: number;
  matched_candidates: number;
  results: MatchedCandidate[];
}

export default function JobMatcher() {
  const [jobDescription, setJobDescription] = useState('');
  const [textWeight, setTextWeight] = useState(0.7);
  const [skillWeight, setSkillWeight] = useState(0.3);
  const [limit, setLimit] = useState(10);

  const [results, setResults] = useState<MatchedCandidate[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [totalCandidates, setTotalCandidates] = useState(0);
  const [searchTerm, setSearchTerm] = useState('');

  const handleMatch = async () => {
    if (!jobDescription.trim()) {
      setError('Please enter a job description (min 50 characters)');
      return;
    }

    if (jobDescription.trim().length < 50) {
      setError('Job description must be at least 50 characters');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const response = await fetch('http://127.0.0.1:8000/api/v1/match', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          job_description: jobDescription,
          text_weight: textWeight,
          skill_weight: skillWeight,
          limit: limit,
        }),
      });

      if (!response.ok) {
        const data = await response.json();
        setError(data.detail || 'Matching failed');
        return;
      }

      const data: MatchResponse = await response.json();
      setResults(data.results);
      setTotalCandidates(data.total_candidates);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to connect to API'
      );
    } finally {
      setLoading(false);
    }
  };

  // Filter results by search term
  const filteredResults = results.filter(
    (r) =>
      r.name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      r.email?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      r.category?.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Job Matcher</h1>
          <p className="text-gray-600 mt-2">
            Match your candidate database against a job description
          </p>
        </div>

        {/* Input Section */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
          {/* Job Description */}
          <div className="lg:col-span-2">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Job Description *
            </label>
            <textarea
              value={jobDescription}
              onChange={(e) => setJobDescription(e.target.value)}
              placeholder="Paste the job description here (min 50 characters)..."
              className="w-full h-40 p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
            <p className="text-xs text-gray-500 mt-1">
              {jobDescription.length} characters
            </p>
          </div>

          {/* Settings */}
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Text Weight
              </label>
              <input
                type="range"
                min="0"
                max="1"
                step="0.1"
                value={textWeight}
                onChange={(e) => {
                  const val = parseFloat(e.target.value);
                  setTextWeight(val);
                  setSkillWeight(1 - val);
                }}
                className="w-full"
              />
              <p className="text-xs text-gray-600">{textWeight.toFixed(1)}</p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Skill Weight
              </label>
              <input
                type="range"
                min="0"
                max="1"
                step="0.1"
                value={skillWeight}
                onChange={(e) => {
                  const val = parseFloat(e.target.value);
                  setSkillWeight(val);
                  setTextWeight(1 - val);
                }}
                className="w-full"
              />
              <p className="text-xs text-gray-600">{skillWeight.toFixed(1)}</p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Results to Show
              </label>
              <select
                value={limit}
                onChange={(e) => setLimit(parseInt(e.target.value))}
                className="w-full p-2 border border-gray-300 rounded-lg"
              >
                {[5, 10, 20, 50, 100].map((n) => (
                  <option key={n} value={n}>
                    Top {n}
                  </option>
                ))}
              </select>
            </div>

            <button
              onClick={handleMatch}
              disabled={loading}
              className="w-full bg-blue-600 text-white py-2 px-4 rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Matching...' : 'Find Matches'}
            </button>
          </div>
        </div>

        {/* Error Message */}
        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
            <p className="text-red-800">{error}</p>
          </div>
        )}

        {/* Results Section */}
        {results.length > 0 && (
          <div className="bg-white rounded-lg shadow">
            {/* Results Header */}
            <div className="border-b border-gray-200 p-6">
              <h2 className="text-xl font-bold text-gray-900">
                Results ({filteredResults.length} / {results.length})
              </h2>
              <p className="text-sm text-gray-600">
                Total candidates scanned: {totalCandidates}
              </p>
              {results.length > 5 && (
                <input
                  type="text"
                  placeholder="Search by name, email, or category..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="mt-3 w-full max-w-md p-2 border border-gray-300 rounded-lg text-sm"
                />
              )}
            </div>

            {/* Results Table */}
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-50 border-b border-gray-200">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-700 uppercase">
                      Name
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-700 uppercase">
                      Category
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-700 uppercase">
                      Scores
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-700 uppercase">
                      Matched Skills
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-700 uppercase">
                      Contact
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {filteredResults.map((candidate) => (
                    <tr
                      key={candidate.candidate_id}
                      className="border-b border-gray-200 hover:bg-gray-50"
                    >
                      <td className="px-6 py-4">
                        <div className="font-medium text-gray-900">
                          {candidate.name || '(No name)'}
                        </div>
                      </td>
                      <td className="px-6 py-4 text-sm">
                        <div className="text-gray-900">{candidate.category}</div>
                        <div className="text-gray-600 text-xs">
                          {candidate.subcategory}
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex flex-col gap-1 text-sm">
                          <div className="flex items-center gap-2">
                            <span className="text-gray-600">Match:</span>
                            <ScoreBar
                              score={candidate.final_score}
                              label={`${(candidate.final_score * 100).toFixed(0)}%`}
                            />
                          </div>
                          <div className="text-xs text-gray-600">
                            Text: {(candidate.similarity_score * 100).toFixed(0)}% | Skills:{' '}
                            {(candidate.skill_match_score * 100).toFixed(0)}%
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4 text-sm">
                        {candidate.matched_skills.length > 0 ? (
                          <div className="flex flex-wrap gap-1">
                            {candidate.matched_skills.slice(0, 3).map((skill) => (
                              <span
                                key={skill}
                                className="inline-block px-2 py-1 text-xs rounded-full bg-green-100 text-green-800"
                              >
                                {skill}
                              </span>
                            ))}
                            {candidate.matched_skills.length > 3 && (
                              <span className="text-xs text-gray-600">
                                +{candidate.matched_skills.length - 3} more
                              </span>
                            )}
                          </div>
                        ) : (
                          <span className="text-gray-500 text-xs">No skill match</span>
                        )}
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-600">
                        <div>{candidate.email || '—'}</div>
                        <div className="text-xs">{candidate.phone || '—'}</div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {filteredResults.length === 0 && (
              <div className="p-6 text-center text-gray-600">
                No results match your search.
              </div>
            )}
          </div>
        )}

        {!loading && results.length === 0 && !error && totalCandidates > 0 && (
          <div className="p-6 text-center text-gray-600 bg-gray-50 rounded-lg">
            <p>No candidates in the system yet. Upload CVs to get started.</p>
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * Simple score bar visualization
 */
function ScoreBar({
  score,
  label,
}: {
  score: number;
  label: string;
}) {
  const getColor = (s: number) => {
    if (s >= 0.8) return 'bg-green-500';
    if (s >= 0.6) return 'bg-yellow-500';
    if (s >= 0.4) return 'bg-orange-500';
    return 'bg-red-500';
  };

  return (
    <div className="flex items-center gap-2">
      <div className="w-24 h-2 bg-gray-200 rounded-full overflow-hidden">
        <div
          className={`h-full ${getColor(score)} transition-all`}
          style={{ width: `${score * 100}%` }}
        />
      </div>
      <span className="text-xs font-medium text-gray-700 min-w-12">{label}</span>
    </div>
  );
}
