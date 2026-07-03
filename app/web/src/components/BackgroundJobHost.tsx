import { useBackgroundJob } from "../hooks/useBackgroundJob";

/** Keeps background-job toast handlers alive app-wide (survives route changes). */
export default function BackgroundJobHost() {
  useBackgroundJob();
  return null;
}
