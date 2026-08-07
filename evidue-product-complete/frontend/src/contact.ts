export const contactEmail = "chagdhar@gmail.com";
export const contactHref = `mailto:${contactEmail}?subject=Evidue%20product%20feedback`;

export type ContactSubmission = {
  name: string;
  email: string;
  company: string;
  discussionType: "Product feedback" | "Invoice review" | "Partnership" | "Other";
  message: string;
};
