"use client";

import {
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";
import { CheckCircle2, LoaderCircle, Send } from "lucide-react";
import type { Dictionary } from "@/lib/site";
import {
  ecosystems,
  experiences,
  limits,
  parseContactResponse,
  reasons,
  validateContact,
  type ContactErrorCode,
  type ContactField,
  type Ecosystem,
  type FieldErrors,
} from "@/lib/contact/validation";
import { Button } from "./ui/button";
import { Checkbox } from "./ui/checkbox";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { NativeSelect } from "./ui/native-select";
import { Textarea } from "./ui/textarea";

type Copy = Dictionary["contact"];

function Field({
  name,
  label,
  optional,
  t,
  errors,
  children,
}: {
  name: ContactField;
  label: string;
  optional?: boolean;
  t: Copy;
  errors: FieldErrors;
  children: ReactNode;
}) {
  return (
    <div className="min-w-0 space-y-2">
      <Label htmlFor={`contact-${name}`}>
        {label}{" "}
        <span className="font-normal text-muted-foreground">
          {optional ? t.optional : t.required}
        </span>
      </Label>
      {children}
      {errors[name] && (
        <p
          id={`contact-${name}-error`}
          className="text-sm leading-6 text-red-700 dark:text-red-300"
        >
          {t.validation[errors[name]]}
        </p>
      )}
    </div>
  );
}

export function ContactForm({ t }: { t: Copy }) {
  const [reason, setReason] = useState("");
  const [privacy, setPrivacy] = useState(false);
  const [selected, setSelected] = useState<Ecosystem[]>([]);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [failure, setFailure] = useState<ContactErrorCode | null>(null);
  const [pending, setPending] = useState(false);
  const [sent, setSent] = useState(false);
  const inFlight = useRef(false);
  const feedback = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (sent || (failure && failure !== "CONTACT_INVALID"))
      feedback.current?.focus();
  }, [sent, failure]);

  function fieldProps(name: ContactField) {
    return {
      id: `contact-${name}`,
      name,
      "aria-invalid": Boolean(errors[name]),
      "aria-describedby": errors[name] ? `contact-${name}-error` : undefined,
    };
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (inFlight.current || sent) return;
    const form = event.currentTarget;
    const data = new FormData(form);
    const result = validateContact({
      name: data.get("name"),
      email: data.get("email"),
      company: data.get("company"),
      subject: data.get("subject"),
      message: data.get("message"),
      reason,
      privacy,
      country: data.get("country") ?? "",
      experience: data.get("experience") ?? "",
      ecosystems: selected,
      website: data.get("website") ?? "",
    });
    if (!result.ok) {
      setErrors(result.fieldErrors);
      setFailure(result.code);
      const first = Object.keys(result.fieldErrors)[0];
      if (first)
        requestAnimationFrame(() =>
          document.getElementById(`contact-${first}`)?.focus(),
        );
      return;
    }
    inFlight.current = true;
    setPending(true);
    setFailure(null);
    setErrors({});
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 65000);
    try {
      const response = await fetch("/api/contact", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...result.data, website: "" }),
        signal: controller.signal,
      });
      const body: unknown = await response.json();
      const outcome = parseContactResponse(body);
      if (response.ok && outcome?.ok) setSent(true);
      else if (outcome && !outcome.ok) {
        setErrors(outcome.fieldErrors ?? {});
        setFailure(outcome.code);
        const first = Object.keys(outcome.fieldErrors ?? {})[0];
        if (first)
          requestAnimationFrame(() =>
            document.getElementById(`contact-${first}`)?.focus(),
          );
      } else setFailure("CONTACT_DELIVERY_FAILED");
    } catch {
      setFailure("CONTACT_DELIVERY_FAILED");
    } finally {
      window.clearTimeout(timeout);
      inFlight.current = false;
      setPending(false);
    }
  }

  if (sent)
    return (
      <div
        ref={feedback}
        tabIndex={-1}
        role="status"
        className="rounded-xl border border-border bg-card p-7 sm:p-10"
      >
        <CheckCircle2 aria-hidden="true" className="mb-6 size-9 text-accent" />
        <h2 className="text-2xl font-medium tracking-tight">
          {t.successTitle}
        </h2>
        <p className="mt-4 text-base leading-7 text-muted-foreground">
          {t.successMessage}
        </p>
        <p className="mt-5 text-sm leading-7 text-muted-foreground">
          {t.testingNote}
        </p>
      </div>
    );

  return (
    <form
      method="post"
      action="/api/contact"
      onSubmit={submit}
      noValidate
      aria-label={t.formTitle}
      aria-busy={pending}
      className="rounded-xl border border-border bg-card p-5 sm:p-8"
    >
      <h2 className="text-2xl font-medium tracking-tight">{t.formTitle}</h2>
      <p className="mt-3 text-sm leading-6 text-muted-foreground">
        {t.formHint}
      </p>
      <noscript>
        <p className="mt-4 text-sm">{t.javascriptNote}</p>
      </noscript>
      <fieldset disabled={pending} className="mt-8 min-w-0 space-y-6">
        <legend className="sr-only">{t.formTitle}</legend>
        <div className="grid gap-6 sm:grid-cols-2">
          <Field name="name" label={t.fields.name} t={t} errors={errors}>
            <Input
              {...fieldProps("name")}
              required
              maxLength={limits.name}
              autoComplete="name"
            />
          </Field>
          <Field name="email" label={t.fields.email} t={t} errors={errors}>
            <Input
              {...fieldProps("email")}
              type="email"
              required
              maxLength={limits.email}
              autoComplete="email"
              spellCheck={false}
              autoCapitalize="none"
            />
          </Field>
        </div>
        <Field
          name="company"
          label={t.fields.company}
          optional
          t={t}
          errors={errors}
        >
          <Input
            {...fieldProps("company")}
            maxLength={limits.company}
            autoComplete="organization"
          />
        </Field>
        <Field name="reason" label={t.fields.reason} t={t} errors={errors}>
          <NativeSelect
            {...fieldProps("reason")}
            required
            value={reason}
            onChange={(event) => {
              setReason(event.target.value);
              setSelected([]);
            }}
          >
            <option value="">{t.selectReason}</option>
            {reasons.map((value) => (
              <option key={value} value={value}>
                {t.reasons[value]}
              </option>
            ))}
          </NativeSelect>
        </Field>
        {reason === "testing" && (
          <div className="space-y-5 rounded-lg border border-border bg-muted/35 p-4 sm:p-5">
            <div>
              <h3 className="font-medium">{t.testingTitle}</h3>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                {t.testingHint}
              </p>
            </div>
            <div className="grid gap-5 sm:grid-cols-2">
              <Field
                name="country"
                label={t.fields.country}
                optional
                t={t}
                errors={errors}
              >
                <Input
                  {...fieldProps("country")}
                  autoComplete="country-name"
                  maxLength={limits.country}
                />
              </Field>
              <Field
                name="experience"
                label={t.fields.experience}
                optional
                t={t}
                errors={errors}
              >
                <NativeSelect {...fieldProps("experience")} defaultValue="">
                  <option value="">{t.selectOptional}</option>
                  {experiences.map((value) => (
                    <option key={value} value={value}>
                      {t.experiences[value]}
                    </option>
                  ))}
                </NativeSelect>
              </Field>
            </div>
            <fieldset {...fieldProps("ecosystems")} tabIndex={-1}>
              <legend className="text-sm leading-6 font-medium">
                {t.fields.ecosystems}{" "}
                <span className="font-normal text-muted-foreground">
                  {t.optional}
                </span>
              </legend>
              <div className="mt-3 grid gap-2 sm:grid-cols-2">
                {ecosystems.map((value) => (
                  <div key={value} className="flex items-start gap-3">
                    <Checkbox
                      id={`ecosystem-${value}`}
                      checked={selected.includes(value)}
                      onCheckedChange={(checked) =>
                        setSelected((current) =>
                          checked
                            ? value === "none"
                              ? ["none"]
                              : [
                                  ...current.filter(
                                    (item) => item !== "none" && item !== value,
                                  ),
                                  value,
                                ]
                            : current.filter((item) => item !== value),
                        )
                      }
                    />
                    <Label
                      className="min-h-9 flex-1 font-normal"
                      htmlFor={`ecosystem-${value}`}
                    >
                      {t.ecosystems[value]}
                    </Label>
                  </div>
                ))}
              </div>
              {errors.ecosystems && (
                <p
                  id="contact-ecosystems-error"
                  className="mt-2 text-sm text-red-700 dark:text-red-300"
                >
                  {t.validation[errors.ecosystems]}
                </p>
              )}
            </fieldset>
          </div>
        )}
        <Field name="subject" label={t.fields.subject} t={t} errors={errors}>
          <Input
            {...fieldProps("subject")}
            required
            maxLength={limits.subject}
          />
        </Field>
        <Field name="message" label={t.fields.message} t={t} errors={errors}>
          <Textarea
            {...fieldProps("message")}
            required
            maxLength={limits.message}
            rows={7}
          />
          <p className="text-xs text-muted-foreground">{t.messageHint}</p>
        </Field>
        <div
          aria-hidden="true"
          className="absolute -left-[10000px] top-auto h-px w-px overflow-hidden"
        >
          <label htmlFor="contact-website">{t.honeypotLabel}</label>
          <input
            id="contact-website"
            name="website"
            type="text"
            tabIndex={-1}
            autoComplete="off"
            maxLength={200}
          />
        </div>
        <div>
          <div className="flex items-start gap-3">
            <Checkbox
              {...fieldProps("privacy")}
              required
              checked={privacy}
              onCheckedChange={(checked) => setPrivacy(checked === true)}
            />
            <Label htmlFor="contact-privacy" className="font-normal">
              {t.privacyAcknowledgement}{" "}
              <span className="text-muted-foreground">{t.required}</span>
            </Label>
          </div>
          {errors.privacy && (
            <p
              id="contact-privacy-error"
              className="mt-2 text-sm leading-6 text-red-700 dark:text-red-300"
            >
              {t.validation[errors.privacy]}
            </p>
          )}
          <p className="mt-3 text-xs leading-6 text-muted-foreground">
            {t.privacyNote}
          </p>
        </div>
      </fieldset>
      {failure && (
        <div
          ref={feedback}
          tabIndex={-1}
          role="alert"
          className="mt-6 rounded-lg border border-red-700/30 bg-red-700/5 p-4 text-sm leading-7 text-red-800 dark:text-red-200"
        >
          {t.errors[failure]}
        </div>
      )}
      <Button
        type="submit"
        disabled={pending}
        className="mt-7 w-full sm:w-auto"
      >
        {pending ? (
          <LoaderCircle
            aria-hidden="true"
            className="motion-safe:animate-spin"
          />
        ) : (
          <Send aria-hidden="true" />
        )}
        {pending ? t.sending : t.send}
      </Button>
      <p role="status" className="sr-only">
        {pending ? t.sending : ""}
      </p>
    </form>
  );
}
