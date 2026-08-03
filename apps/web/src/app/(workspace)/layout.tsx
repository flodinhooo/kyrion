import { AppShell } from "@/components/app-shell";
import { currentUser } from "@/lib/server-auth";
import { redirect } from "next/navigation";

export default async function WorkspaceLayout({ children }: { children: React.ReactNode }) {
  const user = await currentUser();
  if (!user) redirect("/login");
  return <AppShell username={user.username}>{children}</AppShell>;
}
