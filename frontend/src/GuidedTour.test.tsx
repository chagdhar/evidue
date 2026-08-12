import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import GuidedTour, { GuidedTourStep } from "./GuidedTour";

const steps: GuidedTourStep[] = [
  { selector: '[data-tour="one"]', kicker: "ONE", title: "First panel", body: "First explanation." },
  { selector: '[data-tour="two"]', kicker: "TWO", title: "Second panel", body: "Second explanation." },
];

beforeEach(() => {
  window.localStorage.clear();
  Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
    configurable: true,
    value: vi.fn(),
  });
});

afterEach(() => {
  vi.restoreAllMocks();
  window.localStorage.clear();
});

it("runs once on first visit and can be completed", async () => {
  const user = userEvent.setup();
  const { rerender } = render(
    <>
      <div data-tour="one">One</div>
      <div data-tour="two">Two</div>
      <GuidedTour storageKey="tour-test" steps={steps} />
    </>,
  );

  expect(await screen.findByRole("dialog", { name: "First panel" })).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Next" }));
  expect(await screen.findByRole("dialog", { name: "Second panel" })).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Start exploring" }));
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(window.localStorage.getItem("tour-test")).toBe("complete");

  rerender(
    <>
      <div data-tour="one">One</div>
      <div data-tour="two">Two</div>
      <GuidedTour storageKey="tour-test" steps={steps} />
    </>,
  );
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

it("replays after completion when the replay token changes", async () => {
  const user = userEvent.setup();
  window.localStorage.setItem("tour-test", "complete");
  const { rerender } = render(
    <>
      <div data-tour="one">One</div>
      <div data-tour="two">Two</div>
      <GuidedTour storageKey="tour-test" steps={steps} replayToken={0} />
    </>,
  );

  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  rerender(
    <>
      <div data-tour="one">One</div>
      <div data-tour="two">Two</div>
      <GuidedTour storageKey="tour-test" steps={steps} replayToken={1} />
    </>,
  );
  expect(await screen.findByRole("dialog", { name: "First panel" })).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Skip tour" }));
});
