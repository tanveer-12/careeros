export const mockResume = {
  name: "Alex Johnson",
  skills: ["Python", "SQL", "Excel", "Financial Modeling", "Data Analysis"],
  experience_years: 3.5,
  current_role: "Business Analyst",
}

export const mockClusters = [
  {
    id: "1",
    name: "Data Engineering",
    fit: 87,
    icon: "Database",
    skills_present: ["Python", "SQL"],
    skills_missing: ["dbt", "Airflow", "Spark"],
  },
  {
    id: "2",
    name: "Financial Analysis",
    fit: 71,
    icon: "TrendingUp",
    skills_present: ["Excel", "Financial Modeling"],
    skills_missing: ["Bloomberg", "VBA"],
  },
  {
    id: "3",
    name: "Product Management",
    fit: 63,
    icon: "Layers",
    skills_present: ["SQL", "Data Analysis"],
    skills_missing: ["Roadmapping", "Figma"],
  },
]

export const mockPlan = {
  cluster: "Data Engineering",
  duration_weeks: 8,
  weeks: [
    {
      week: 1,
      actions: [
        { task: "Learn dbt fundamentals", hours: 3 },
        { task: "Complete Airflow intro tutorial", hours: 4 },
        { task: "Apply to 2 entry Data Engineering roles", hours: 1 },
      ],
    },
    {
      week: 2,
      actions: [
        { task: "Build a dbt project on public dataset", hours: 5 },
        { task: "Read Fundamentals of Data Engineering Ch. 1-3", hours: 3 },
        { task: "Apply to 3 more roles with updated resume", hours: 1 },
      ],
    },
  ],
}
