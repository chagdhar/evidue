import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Link, MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import ScrollToTop from "./ScrollToTop";

afterEach(() => vi.restoreAllMocks());

it("returns to the top when navigation changes the route", async () => {
  const scrollTo = vi.spyOn(window, "scrollTo").mockImplementation(() => undefined);
  const user = userEvent.setup();
  render(
    <MemoryRouter initialEntries={["/try"]}>
      <ScrollToTop />
      <Routes>
        <Route path="/try" element={<Link to="/contact">Contact</Link>} />
        <Route path="/contact" element={<h1>Contact page</h1>} />
      </Routes>
    </MemoryRouter>,
  );

  scrollTo.mockClear();
  await user.click(screen.getByRole("link", { name: "Contact" }));
  expect(await screen.findByRole("heading", { name: "Contact page" })).toBeInTheDocument();
  expect(scrollTo).toHaveBeenCalledWith({ top: 0, left: 0, behavior: "auto" });
});
