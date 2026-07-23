import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DocumentAnswerIcon } from "@/components/DocumentAnswerIcon";

describe("DocumentAnswerIcon", () => {
  it("renderiza SVG decorativo e fora da navegação por teclado", () => {
    render(<DocumentAnswerIcon className="test-icon" />);

    const icon = screen.getByTestId("document-answer-icon");
    expect(icon.tagName.toLowerCase()).toBe("svg");
    expect(icon).toHaveAttribute("aria-hidden", "true");
    expect(icon).toHaveAttribute("focusable", "false");
    expect(icon).toHaveAttribute("viewBox", "0 0 220 180");
    expect(icon).toHaveClass("test-icon");
    expect(icon).not.toHaveAttribute("role", "button");
  });
});
