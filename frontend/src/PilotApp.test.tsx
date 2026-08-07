import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";
import PilotApp from "./PilotApp";

describe("Evidue reconciliation workspace", () => {
  beforeEach(() => sessionStorage.clear());

  it("requires a workspace access key before exposing customer data controls", () => {
    render(
      <MemoryRouter initialEntries={["/pilot"]}>
        <PilotApp />
      </MemoryRouter>,
    );
    expect(screen.getByRole("heading", { name: /open your finance workspace/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/access key/i)).toHaveAttribute("type", "password");
    expect(screen.queryByText(/choose invoice csv/i)).not.toBeInTheDocument();
  });
});
