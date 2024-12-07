questions = {
  "initial_messages": [
    {"welcome": """Welcome, {name}, and thank you for taking the time to interview with us today for the {position} position at {company}.

We\'re excited to learn more about your background, experience, and how you might contribute to our mission of {company_mission}. 

Here\'s what to expect during today\'s interview:

1. You\'ll be asked a series of questions designed to explore your:
   - Technical expertise,
   - Problem-solving abilities,
   - Adaptability,
   - Collaboration skills, and
   - Alignment with our company values.
   
2. Feel free to take your time with each question, and don\'t hesitate to ask for clarification or additional context if needed.

At the end of the interview, you\'ll receive information about the next steps, and you\'ll also have an opportunity to share any final remarks or questions.

Before we begin, do you have any questions about the process, or are you ready to get started?

When you\'re ready, just let me know!"""
    },
    {
    "question": "To start, could you tell us a bit about yourself and what attracted you to this role?",
    "competency": "General Introduction"
    }
  ],
  "interview_questions": {
    "behavioral": [
      {
        "question": "Can you describe a situation where you encountered a significant technical challenge in a project? What steps did you take to resolve it, and what was the result?",
        "competency": "Problem-Solving"
      },
      {
        "question": "Tell us about a time when you implemented an LLM-based solution (e.g., conversational AI, RAG). What was the problem, what tools or techniques did you use, and what were the outcomes?",
        "competency": "Technical Expertise"
      },
      {
        "question": "Describe a project where you had to work closely with cross-functional teams, such as product managers or designers. How did you ensure effective communication and alignment, and what was the result?",
        "competency": "Collaboration"
      },
      {
        "question": "Can you share an experience where a project\'s requirements changed significantly mid-way? How did you adapt, and what was the ultimate outcome?",
        "competency": "Adaptability"
      },
      {
        "question": "Tell us about a time when you contributed to building or enhancing a collaborative, supportive work culture. What actions did you take, and what impact did it have on the team?",
        "competency": "Cultural Fit"
      }
    ],
    "situational": [
      {
        "question": "Imagine you\'re developing a conversational AI system, and a critical performance issue arises right before launch. How would you approach identifying and resolving the issue under time constraints?",
        "competency": "Problem-Solving"
      },
      {
        "question": "Suppose a client wants to scale a data pipeline to handle 10x the current load in a short timeframe. How would you assess the system and implement necessary changes?",
        "competency": "Technical Expertise"
      },
      {
        "question": "You are tasked with integrating a new, untested LLM tool into an existing workflow. What steps would you take to ensure its successful implementation?",
        "competency": "Technical Expertise"
      },
      {
        "question": "If you were collaborating with a product team that had different priorities from the development team, how would you align goals and move the project forward?",
        "competency": "Collaboration"
      },
      {
        "question": "You\'re juggling multiple projects with competing deadlines. How would you prioritize your tasks and ensure all deliverables are met?",
        "competency": "Adaptability"
      }
    ],
    "technical": [
      {
        "question": "What approaches have you used for prompt engineering, and how have they impacted the performance of your LLM-based systems?",
        "competency": "Technical Expertise"
      },
      {
        "question": "Can you explain how you would design a system that combines vector search with retrieval-augmented generation? What challenges do you foresee, and how would you address them?",
        "competency": "Technical Expertise"
      },
      {
        "question": "Describe a recent Python project you worked on. What challenges did you face, and how did you overcome them?",
        "competency": "Technical Expertise"
      },
      {
        "question": "What steps do you follow to set up a robust CI/CD pipeline for a new application?",
        "competency": "Technical Expertise"
      },
      {
        "question": "What is your approach to debugging a performance bottleneck in a data pipeline? Can you give an example?",
        "competency": "Problem-Solving"
      }
    ],
    "cultural_fit": [
      {
        "question": "Astoria AI\'s mission is to unlock human potential through AI. How does this mission resonate with you, and how do you see yourself contributing to it?",
        "competency": "Cultural Fit"
      },
      {
        "question": "What does human-centric innovation mean to you, and how have you applied it in your past projects?",
        "competency": "Cultural Fit"
      },
      {
        "question": "What does teamwork mean to you, and how have you demonstrated it in your previous roles?",
        "competency": "Collaboration"
      },
      {
        "question": "How do you stay current with emerging trends and tools in AI and software development? Can you share a recent example of how you applied something new you learned?",
        "competency": "Adaptability"
      },
      {
        "question": "How do you approach ethical considerations when developing AI applications, especially those involving user data?",
        "competency": "Cultural Fit"
      }
    ]
  }
}


eval_criteria = {
  "scoring_criteria": {
    "competencies": {
      "Problem-Solving": {
        "1": "Unable to identify root causes of problems or propose solutions.",
        "2": "Proposes basic solutions but lacks depth in analysis or innovation.",
        "3": "Identifies root causes effectively and suggests reasonable solutions.",
        "4": "Provides innovative solutions and anticipates potential issues.",
        "5": "Solves problems efficiently, proposing robust, forward-thinking solutions."
      },
      "Technical Expertise": {
        "1": "Minimal knowledge of required tools, languages, or techniques.",
        "2": "Basic familiarity but lacks hands-on experience.",
        "3": "Adequate technical skills for the role, with some advanced knowledge.",
        "4": "Strong technical skills with a proven track record of success.",
        "5": "Mastery of tools, techniques, and best practices; exceeds expectations."
      },
      "Leadership": {
        "1": "Rarely takes initiative or demonstrates leadership abilities.",
        "2": "Occasionally leads but lacks consistency or team alignment.",
        "3": "Demonstrates reliable leadership and team collaboration.",
        "4": "Inspires others and effectively manages challenges.",
        "5": "Consistently leads with vision, inspiring high performance in others."
      },
      "Adaptability": {
        "1": "Struggles with change; requires significant guidance.",
        "2": "Adapts slowly or with difficulty.",
        "3": "Adapts to change with minimal guidance.",
        "4": "Adapts quickly and with confidence.",
        "5": "Thrives in dynamic environments, proactively driving positive change."
      },
      "Collaboration": {
        "1": "Difficulty working with others; lacks communication skills.",
        "2": "Works with others but struggles with effective collaboration.",
        "3": "Communicates and collaborates effectively with teams.",
        "4": "Builds strong, productive relationships within the team.",
        "5": "Exemplifies team synergy, fosters collaboration, and mentors others."
      },
      "Cultural Fit": {
        "1": "Values and goals misaligned with company culture.",
        "2": "Partial alignment but lacks enthusiasm for the mission.",
        "3": "Understands and generally aligns with company values.",
        "4": "Strong alignment with mission and actively demonstrates shared values.",
        "5": "Embodies company culture and promotes its values passionately."
      }
    }
  }
}