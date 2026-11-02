// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import LoginPage from "../app/login/page";

const mockRouter = { push: vi.fn(), refresh: vi.fn() };
const mockSignInWithPassword = vi.fn();

vi.mock("next/navigation", () => ({ useRouter: () => mockRouter }));
vi.mock("@/lib/supabase/client", () => ({
  createSupabaseBrowserClient: () => ({ auth: { signInWithPassword: mockSignInWithPassword } }),
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("inicio de sesión por contraseña", () => {
  it("muestra únicamente correo y contraseña y una acción de inicio de sesión", () => {
    render(<LoginPage />);

    expect(screen.getAllByRole("textbox")).toHaveLength(1);
    expect(screen.getByLabelText("Correo electrónico").getAttribute("type")).toBe("email");
    expect(screen.getByLabelText("Contraseña").getAttribute("type")).toBe("password");
    expect(document.querySelectorAll("input")).toHaveLength(2);
    expect(screen.getAllByRole("button")).toHaveLength(1);
    expect(screen.getByRole("button", { name: "Iniciar sesión" })).toBeTruthy();
    expect(screen.queryByText(/código|enlace mágico|recuperar contraseña|registr/i)).toBeNull();
  });

  it("autentica con contraseña y abre directamente el simulador", async () => {
    mockSignInWithPassword.mockResolvedValue({ error: null });
    render(<LoginPage />);

    fireEvent.change(screen.getByLabelText("Correo electrónico"), { target: { value: " user@example.org " } });
    fireEvent.change(screen.getByLabelText("Contraseña"), { target: { value: "a-private-password" } });
    fireEvent.click(screen.getByRole("button", { name: "Iniciar sesión" }));

    await vi.waitFor(() => expect(mockSignInWithPassword).toHaveBeenCalledWith({ email: "user@example.org", password: "a-private-password" }));
    expect(mockRouter.push).toHaveBeenCalledWith("/lab");
    expect(mockRouter.refresh).toHaveBeenCalledOnce();
  });

  it("no navega cuando Supabase rechaza las credenciales", async () => {
    mockSignInWithPassword.mockResolvedValue({ error: new Error("invalid credentials") });
    render(<LoginPage />);

    fireEvent.change(screen.getByLabelText("Correo electrónico"), { target: { value: "user@example.org" } });
    fireEvent.change(screen.getByLabelText("Contraseña"), { target: { value: "wrong-password" } });
    fireEvent.click(screen.getByRole("button", { name: "Iniciar sesión" }));

    expect((await screen.findByRole("alert")).textContent).toMatch(/correo.*contraseña/i);
    expect(mockRouter.push).not.toHaveBeenCalled();
  });
});
