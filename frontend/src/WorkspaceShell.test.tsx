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
  it("presents the invoice-centered finance-control information architecture", () => {
    render(
      <MemoryRouter initialEntries={["/workspace"]}>
        <WorkspaceShell active="overview" workspaceId="acme-finance"><LocationProbe /></WorkspaceShell>
      </MemoryRouter>,
    );

    expect(screen.getByRole("button", { name: "Overview" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("button", { name: "Invoices" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Review queue" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Vendors" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Settings" })).toBeInTheDocument();
    expect(screen.queryByText(/finance operations/i)).not.toBeInTheDocument();
  });

  it("navigates between workspace surfaces without leaving the workspace", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/workspace"]}>
        <WorkspaceShell active="overview"><LocationProbe /></WorkspaceShell>
      </MemoryRouter>,
    );

    await user.click(screen.getByRole("button", { name: "Review queue" }));
    expect(screen.getByTestId("location")).toHaveTextContent("/workspace/review");
  });
});
