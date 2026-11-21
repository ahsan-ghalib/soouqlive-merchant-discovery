import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatNumber(value: number | undefined | null) {
  if (value == null) return "0";
  return new Intl.NumberFormat("en-SA").format(value);
}
