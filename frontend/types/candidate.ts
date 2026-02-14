export type TargetRole = "baker" | "cashier" | "delivery_driver";

export interface Candidate {
  id: string;
  fullName: string;
  phoneNumber: string;
  email?: string;
  targetRole: TargetRole;
  applicationSource?: string;
  createdAt: string;
  updatedAt: string;
}
