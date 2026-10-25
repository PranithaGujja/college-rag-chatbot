import type { Role } from "./api";

// Full class names are written out so Tailwind can detect them.
export const THEME: Record<Role, {
  label: string; handbook: string; assistant: string; blurb: string;
  badge: string; accent: string; accentHover: string; ring: string; soft: string; softText: string; userBubble: string; gradient: string;
  suggestions: string[];
}> = {
  student: {
    label: "Student", handbook: "Student Handbook", assistant: "Student Handbook Assistant",
    blurb: "Ask anything about attendance, exams, grading, conduct, hostels and more.",
    badge: "bg-indigo-100 text-indigo-800", accent: "bg-indigo-600", accentHover: "hover:bg-indigo-700", ring: "focus:ring-indigo-500 focus:border-indigo-500",
    soft: "bg-indigo-50 border-indigo-200", softText: "text-indigo-700", userBubble: "bg-indigo-600 text-white", gradient: "from-indigo-600 to-blue-700",
    suggestions: [
      "What is the minimum attendance requirement?",
      "How is CGPA calculated?",
      "What is the punishment for ragging?",
      "What are the hostel rules?",
      "Can I change my branch?",
    ],
  },
  faculty: {
    label: "Faculty", handbook: "Faculty Handbook", assistant: "Faculty Handbook Assistant",
    blurb: "Ask anything about leave, workload, duties, benefits, policies and more.",
    badge: "bg-emerald-100 text-emerald-800", accent: "bg-emerald-600", accentHover: "hover:bg-emerald-700", ring: "focus:ring-emerald-500 focus:border-emerald-500",
    soft: "bg-emerald-50 border-emerald-200", softText: "text-emerald-700", userBubble: "bg-emerald-600 text-white", gradient: "from-emerald-600 to-teal-700",
    suggestions: [
      "How many casual leaves can a faculty member take?",
      "What is the maternity leave policy?",
      "What is the teaching workload of a professor?",
      "What are the examination duties of faculty?",
      "What is the dress code for staff?",
    ],
  },
};
