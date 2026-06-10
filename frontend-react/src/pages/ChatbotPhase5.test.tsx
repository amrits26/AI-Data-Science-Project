import { cleanup, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import Chatbot from "./Chatbot"

const mockApi = vi.hoisted(() => ({
  askDetailed: vi.fn(),
  submitTriage: vi.fn(),
  resumeDeal: vi.fn(),
}))

vi.mock("../services/api", () => ({
  api: mockApi,
}))

describe("Phase 5 Voice Input", () => {
  afterEach(() => {
    cleanup()
  })

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("shows fallback message when SpeechRecognition is unavailable", async () => {
    render(<Chatbot />)

    await userEvent.click(screen.getByRole("button", { name: /Use voice input/i }))

    expect(await screen.findByText(/Voice input is not supported/i)).toBeInTheDocument()
  })
})
