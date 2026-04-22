import type { Candidate } from "@/components/candidate-card"

type MockCandidate = Candidate & {
  title: string
  yearsOfExperience: number
}

export const mockCandidates: MockCandidate[] = [
  {
    id: "1",
    name: "Sarah Chen",
    email: "sarah.chen@email.com",
    phone: "+1 (555) 123-4567",
    skills: ["React", "TypeScript", "Node.js", "GraphQL", "AWS"],
    yearsOfExperience: 6,
    title: "Senior Frontend Engineer",
  },
  {
    id: "2",
    name: "Michael Rodriguez",
    email: "m.rodriguez@email.com",
    phone: "+1 (555) 234-5678",
    skills: ["Python", "Django", "PostgreSQL", "Docker", "Kubernetes"],
    yearsOfExperience: 8,
    title: "Backend Developer",
  },
  {
    id: "3",
    name: "Emily Watson",
    email: "emily.watson@email.com",
    phone: "+1 (555) 345-6789",
    skills: ["UI/UX Design", "Figma", "CSS", "React", "Tailwind"],
    yearsOfExperience: 4,
    title: "Product Designer",
  },
  {
    id: "4",
    name: "David Kim",
    email: "david.kim@email.com",
    phone: "+1 (555) 456-7890",
    skills: ["Java", "Spring Boot", "Microservices", "MongoDB", "Redis"],
    yearsOfExperience: 10,
    title: "Senior Software Architect",
  },
  {
    id: "5",
    name: "Lisa Thompson",
    email: "lisa.t@email.com",
    phone: "+1 (555) 567-8901",
    skills: ["Data Science", "Python", "TensorFlow", "SQL", "Tableau"],
    yearsOfExperience: 5,
    title: "Data Analyst",
  },
  {
    id: "6",
    name: "James Wilson",
    email: "j.wilson@email.com",
    phone: "+1 (555) 678-9012",
    skills: ["DevOps", "AWS", "Terraform", "CI/CD", "Linux"],
    yearsOfExperience: 7,
    title: "DevOps Engineer",
  },
  {
    id: "7",
    name: "Anna Martinez",
    email: "anna.m@email.com",
    phone: "+1 (555) 789-0123",
    skills: ["iOS", "Swift", "SwiftUI", "Objective-C", "Firebase"],
    yearsOfExperience: 5,
    title: "iOS Developer",
  },
  {
    id: "8",
    name: "Robert Johnson",
    email: "r.johnson@email.com",
    phone: "+1 (555) 890-1234",
    skills: ["Project Management", "Agile", "Scrum", "JIRA", "Confluence"],
    yearsOfExperience: 9,
    title: "Technical Project Manager",
  },
]

export const mockRecentUploads: Array<{
  id: string
  fileName: string
  uploadedAt: Date
  status: "pending" | "completed" | "failed"
  candidateName?: string
}> = [
  {
    id: "1",
    fileName: "sarah_chen_resume.pdf",
    uploadedAt: new Date(Date.now() - 1000 * 60 * 5),
    status: "completed",
    candidateName: "Sarah Chen",
  },
  {
    id: "2",
    fileName: "michael_rodriguez_cv.docx",
    uploadedAt: new Date(Date.now() - 1000 * 60 * 15),
    status: "completed",
    candidateName: "Michael Rodriguez",
  },
  {
    id: "3",
    fileName: "emily_watson_portfolio.pdf",
    uploadedAt: new Date(Date.now() - 1000 * 60 * 30),
    status: "completed",
    candidateName: "Emily Watson",
  },
  {
    id: "4",
    fileName: "unknown_resume_v2.pdf",
    uploadedAt: new Date(Date.now() - 1000 * 60 * 45),
    status: "pending",
  },
  {
    id: "5",
    fileName: "corrupted_file.pdf",
    uploadedAt: new Date(Date.now() - 1000 * 60 * 60),
    status: "failed",
  },
]

export const mockStats = {
  totalUploads: 247,
  parsedCandidates: 234,
  pending: 8,
  failed: 5,
  queueSize: 3,
  activeWorkers: 4,
  processingSpeed: 12,
}

export function getCandidateById(id: string): Candidate | undefined {
  return mockCandidates.find((c) => c.id === id)
}

export const mockCandidateDetails: Record<
  string,
  {
    summary: string
    experience: Array<{
      title: string
      company: string
      startDate: string
      endDate: string
      description: string
    }>
    education: Array<{
      degree: string
      school: string
      year: string
    }>
    rawCV: string
  }
> = {
  "1": {
    summary:
      "Experienced frontend engineer with 6+ years building scalable web applications. Passionate about creating intuitive user experiences with modern technologies.",
    experience: [
      {
        title: "Senior Frontend Engineer",
        company: "TechCorp Inc.",
        startDate: "2021",
        endDate: "Present",
        description:
          "Leading frontend development for the main product. Implemented new React architecture, reducing bundle size by 40%.",
      },
      {
        title: "Frontend Developer",
        company: "StartupXYZ",
        startDate: "2018",
        endDate: "2021",
        description:
          "Built customer-facing dashboards and internal tools using React and TypeScript.",
      },
      {
        title: "Junior Developer",
        company: "WebAgency",
        startDate: "2016",
        endDate: "2018",
        description:
          "Developed responsive websites and web applications for various clients.",
      },
    ],
    education: [
      {
        degree: "B.S. Computer Science",
        school: "State University",
        year: "2016",
      },
    ],
    rawCV: `SARAH CHEN
Senior Frontend Engineer

CONTACT
Email: sarah.chen@email.com
Phone: +1 (555) 123-4567

SUMMARY
Experienced frontend engineer with 6+ years building scalable web applications.

SKILLS
React, TypeScript, Node.js, GraphQL, AWS

EXPERIENCE
Senior Frontend Engineer | TechCorp Inc. | 2021 - Present
- Leading frontend development for the main product
- Implemented new React architecture, reducing bundle size by 40%

Frontend Developer | StartupXYZ | 2018 - 2021
- Built customer-facing dashboards and internal tools
- Used React and TypeScript

Junior Developer | WebAgency | 2016 - 2018
- Developed responsive websites and web applications

EDUCATION
B.S. Computer Science | State University | 2016`,
  },
}

// Generate details for other candidates
for (const candidate of mockCandidates) {
  if (!mockCandidateDetails[candidate.id]) {
    mockCandidateDetails[candidate.id] = {
      summary: `${candidate.title} with ${candidate.yearsOfExperience} years of experience specializing in ${candidate.skills.slice(0, 3).join(", ")}.`,
      experience: [
        {
          title: candidate.title || "Software Engineer",
          company: "Current Company",
          startDate: `${2024 - Math.floor(candidate.yearsOfExperience / 2)}`,
          endDate: "Present",
          description: `Working with ${candidate.skills.slice(0, 3).join(", ")} to build innovative solutions.`,
        },
        {
          title: "Previous Role",
          company: "Previous Company",
          startDate: `${2024 - candidate.yearsOfExperience}`,
          endDate: `${2024 - Math.floor(candidate.yearsOfExperience / 2)}`,
          description: `Developed expertise in ${candidate.skills.slice(0, 2).join(" and ")}.`,
        },
      ],
      education: [
        {
          degree: "Bachelor's Degree",
          school: "University",
          year: `${2024 - candidate.yearsOfExperience - 4}`,
        },
      ],
      rawCV: `${candidate.name.toUpperCase()}
${candidate.title}

CONTACT
Email: ${candidate.email}
Phone: ${candidate.phone}

SKILLS
${candidate.skills.join(", ")}

EXPERIENCE
${candidate.yearsOfExperience} years of professional experience`,
    }
  }
}
