export type ContactDiscussionType = "Product feedback" | "Invoice review" | "Partnership" | "Other";

export type ContactSubmission = {
  name: string;
  email: string;
  company: string;
  role: string;
  discussionType: ContactDiscussionType;
  billingModel: string;
  verificationMethod: string;
  evidenceLocation: string;
  commercialAction: string;
  feedbackArea: string;
  message: string;
  openToCall: boolean;
};
