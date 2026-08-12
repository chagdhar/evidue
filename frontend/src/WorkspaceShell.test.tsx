import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router-dom";
import { describe, expect, it } from "vitest";
import WorkspaceShell from "./WorkspaceShell";

function LocationProbe() {
  const location = useLocation();
  return <span data-testid="location">{location.pathname}</span>;
}

describe("customer workspace shell", () => {
  it("presents reconciliation, finance operations, and settings as one product", () => {
    render(
      <MemoryRouter initialEntries={["/workspace"]}>
        <WorkspaceShell active="reconciliation" workspaceId="acme-finance">
          <LocationProbe />
        </WorkspaceShell>
      </MemoryRouter>,
    );

    expect(screen.getByRole("button", { name: "Reconciliation" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("button", { name: "Finance operations" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Settings" })).toBeInTheDocument();
    expect(screen.queryByText(/email dharun/i)).not.toBeInTheDocument();
  });

  it("navigates between workspace surfaces without leaving the workspace", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/workspace"]}>
        <WorkspaceShell active="reconciliation">
          <LocationProbe />
        </WorkspaceShell>
      </MemoryRouter>,
    );

    await user.click(screen.getByRole("button", { name: "Finance operations" }));
    expect(screen.getByTestId("location")).toHaveTextContent("/workspace/operations");
  });
});
