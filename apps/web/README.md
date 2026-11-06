This is a [Next.js](https://nextjs.org) project bootstrapped with [`create-next-app`](https://nextjs.org/docs/app/api-reference/cli/create-next-app).

## Optional Kyrion account

Local sign-in remains independent of the internet. When Core enables central
identity, the login page also offers the standard device authorization flow.
Core verifies the provider identity; the browser presents the user code and an
explicit completion button. A central identity requires an existing linked local
account. Protected first setup and invitation redemption remain the only local
account enrollment paths.

Profile and Settings → Identity expose connection status, password-confirmed
connection and disconnection. First setup can proceed locally or lead to the
connection panel after creating the protected local account. No local rights or
passwords are synchronized. Device operation credentials stay in a path-scoped
HttpOnly cookie; mutating BFF endpoints require the existing CSRF proof and reject
foreign Origins. Session credentials stay server-side/HttpOnly. See
`docs/agent-handoffs/unified-identity-handover.md` for provider configuration,
security boundaries and acceptance evidence.

## Getting Started

First, run the development server:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

You can start editing the page by modifying `app/page.tsx`. The page auto-updates as you edit the file.

This project uses [`next/font`](https://nextjs.org/docs/app/building-your-application/optimizing/fonts) to automatically optimize and load [Geist](https://vercel.com/font), a new font family for Vercel.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for more details.
