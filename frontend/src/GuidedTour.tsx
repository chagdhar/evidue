import { Box, Button, Paper, Stack, Typography } from "@mui/material";
import { CSSProperties, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";

export type GuidedTourStep = {
  selector: string;
  kicker: string;
  title: string;
  body: string;
};

type Props = {
  storageKey: string;
  steps: GuidedTourStep[];
  replayToken?: number;
  autoStart?: boolean;
  finishSelector?: string;
  finishLabel?: string;
};

type TargetRect = {
  top: number;
  left: number;
  right: number;
  bottom: number;
  width: number;
  height: number;
};

const EDGE = 16;
const PAD = 8;
const DESKTOP_TOOLTIP_WIDTH = 380;
const TOOLTIP_HEIGHT_ESTIMATE = 270;

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}

function hasCompletedTour(storageKey: string) {
  try {
    return window.window.localStorage.getItem(storageKey) === "complete";
  } catch {
    return false;
  }
}

function rememberCompletedTour(storageKey: string) {
  try {
    window.window.localStorage.setItem(storageKey, "complete");
  } catch {
    // Storage can be unavailable in private or hardened browser contexts.
  }
}

export default function GuidedTour({
  storageKey,
  steps,
  replayToken = 0,
  autoStart = true,
  finishSelector,
  finishLabel = "Start exploring",
}: Props) {
  const [open, setOpen] = useState(false);
  const [index, setIndex] = useState(0);
  const [targetRect, setTargetRect] = useState<TargetRect | null>(null);
  const tooltipRef = useRef<HTMLDivElement | null>(null);
  const lastReplayToken = useRef(replayToken);

  const step = steps[index] ?? steps[0];

  useEffect(() => {
    if (!autoStart || typeof window === "undefined" || !steps.length) return;
    if (!hasCompletedTour(storageKey)) {
      setIndex(0);
      setOpen(true);
    }
  }, [autoStart, steps.length, storageKey]);

  useEffect(() => {
    if (replayToken === lastReplayToken.current) return;
    lastReplayToken.current = replayToken;
    setIndex(0);
    setOpen(true);
  }, [replayToken]);

  useEffect(() => {
    if (!open || !step || typeof document === "undefined") return;

    let measureFrame = 0;
    let settleFrame = 0;

    const measure = () => {
      const target = document.querySelector<HTMLElement>(step.selector);
      if (!target) {
        setTargetRect(null);
        return;
      }

      if (typeof target.scrollIntoView === "function") {
        target.scrollIntoView({ behavior: "auto", block: "center", inline: "nearest" });
      }

      settleFrame = window.requestAnimationFrame(() => {
        const rect = target.getBoundingClientRect();
        setTargetRect({
          top: rect.top,
          left: rect.left,
          right: rect.right,
          bottom: rect.bottom,
          width: rect.width,
          height: rect.height,
        });
      });
    };

    measureFrame = window.requestAnimationFrame(measure);
    const refresh = () => measure();
    window.addEventListener("resize", refresh);
    window.addEventListener("scroll", refresh, true);

    return () => {
      window.cancelAnimationFrame(measureFrame);
      window.cancelAnimationFrame(settleFrame);
      window.removeEventListener("resize", refresh);
      window.removeEventListener("scroll", refresh, true);
    };
  }, [index, open, step]);

  useEffect(() => {
    if (!open) return;
    const frame = window.requestAnimationFrame(() => tooltipRef.current?.focus());
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") finish();
      if (event.key === "ArrowRight" && index < steps.length - 1) setIndex((value) => value + 1);
      if (event.key === "ArrowLeft" && index > 0) setIndex((value) => value - 1);

      if (event.key === "Tab" && tooltipRef.current) {
        const focusable = Array.from(
          tooltipRef.current.querySelectorAll<HTMLElement>(
            'button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
          ),
        );
        if (!focusable.length) {
          event.preventDefault();
          tooltipRef.current.focus();
          return;
        }
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.cancelAnimationFrame(frame);
      window.removeEventListener("keydown", handleKeyDown);
    };
  });

  function finish() {
    if (typeof window !== "undefined") rememberCompletedTour(storageKey);
    setOpen(false);
    if (finishSelector && typeof document !== "undefined") {
      window.requestAnimationFrame(() => {
        const target = document.querySelector<HTMLElement>(finishSelector);
        if (target && typeof target.scrollIntoView === "function") {
          target.scrollIntoView({ behavior: "auto", block: "center", inline: "nearest" });
        }
      });
    }
  }

  const tooltipStyle = useMemo<CSSProperties>(() => {
    if (typeof window === "undefined" || !targetRect) {
      return { left: "50%", top: "50%", transform: "translate(-50%, -50%)" };
    }

    if (window.innerWidth < 720) {
      return { left: EDGE, right: EDGE, bottom: EDGE };
    }

    const width = Math.min(DESKTOP_TOOLTIP_WIDTH, window.innerWidth - EDGE * 2);
    const maxTop = Math.max(EDGE, window.innerHeight - TOOLTIP_HEIGHT_ESTIMATE - EDGE);
    const rightRoom = window.innerWidth - targetRect.right - 14;
    const leftRoom = targetRect.left - 14;

    if (rightRoom >= width) {
      return { left: targetRect.right + 14, top: clamp(targetRect.top, EDGE, maxTop), width };
    }

    if (leftRoom >= width) {
      return { left: targetRect.left - width - 14, top: clamp(targetRect.top, EDGE, maxTop), width };
    }

    const left = clamp(
      targetRect.left + targetRect.width / 2 - width / 2,
      EDGE,
      window.innerWidth - width - EDGE,
    );
    const fitsBelow = targetRect.bottom + 14 + TOOLTIP_HEIGHT_ESTIMATE <= window.innerHeight - EDGE;
    if (fitsBelow) return { left, top: targetRect.bottom + 14, width };

    const fitsAbove = targetRect.top - 14 - TOOLTIP_HEIGHT_ESTIMATE >= EDGE;
    if (fitsAbove) return { left, top: targetRect.top - 14 - TOOLTIP_HEIGHT_ESTIMATE, width };

    return { left, top: clamp(targetRect.top + 20, EDGE, maxTop), width };
  }, [targetRect]);

  if (!open || !step || typeof document === "undefined") return null;

  return createPortal(
    <Box className="evidue-tour-root" aria-live="polite">
      <Box className={`evidue-tour-backdrop${targetRect ? " has-target" : ""}`} aria-hidden="true" />
      {targetRect && (
        <Box
          className="evidue-tour-spotlight"
          aria-hidden="true"
          sx={{
            top: Math.max(4, targetRect.top - PAD),
            left: Math.max(4, targetRect.left - PAD),
            width: Math.max(24, targetRect.width + PAD * 2),
            height: Math.max(24, targetRect.height + PAD * 2),
          }}
        />
      )}

      <Paper
        ref={tooltipRef}
        className="evidue-tour-card"
        role="dialog"
        aria-modal="true"
        aria-labelledby="evidue-tour-title"
        aria-describedby="evidue-tour-body"
        tabIndex={-1}
        style={tooltipStyle}
      >
        <Stack spacing={1.6}>
          <Stack direction="row" justifyContent="space-between" alignItems="center" spacing={2}>
            <Typography className="evidue-tour-kicker">{step.kicker}</Typography>
            <Typography className="evidue-tour-count">{index + 1} of {steps.length}</Typography>
          </Stack>

          <Box>
            <Typography id="evidue-tour-title" component="h2" className="evidue-tour-title">
              {step.title}
            </Typography>
            <Typography id="evidue-tour-body" className="evidue-tour-body">{step.body}</Typography>
          </Box>

          <Box className="evidue-tour-progress" aria-hidden="true">
            {steps.map((item, itemIndex) => (
              <span key={`${item.selector}-${itemIndex}`} className={itemIndex <= index ? "active" : ""} />
            ))}
          </Box>

          <Stack direction="row" justifyContent="space-between" alignItems="center" spacing={1}>
            <Button variant="text" onClick={finish}>Skip tour</Button>
            <Stack direction="row" spacing={1}>
              {index > 0 && <Button variant="outlined" onClick={() => setIndex((value) => value - 1)}>Back</Button>}
              {index < steps.length - 1 ? (
                <Button variant="contained" onClick={() => setIndex((value) => value + 1)}>Next</Button>
              ) : (
                <Button variant="contained" onClick={finish}>{finishLabel}</Button>
              )}
            </Stack>
          </Stack>
        </Stack>
      </Paper>
    </Box>,
    document.body,
  );
}
