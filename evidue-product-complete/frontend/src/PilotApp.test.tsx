import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import PilotApp from "./PilotApp";

describe("Evidue reconciliation workspace", () => {
  beforeEach(() => sessionStorage.clear());

  it("requires a workspace access key before exposing customer data controls", () => {
    render(<PilotApp />);
    expect(screen.getByRole("heading", { name: /open your reconciliation workspace/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/workspace access key/i)).toHaveAttribute("type", "password");
    expect(screen.queryByText(/choose invoice csv/i)).not.toBeInTheDocument();
  });
});
