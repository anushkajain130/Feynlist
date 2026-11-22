import DashboardPage from "./DashboardPage";

// Data loads in the browser (DashboardPage) so each request carries the
// evaluator's session id and time zone, and a sleeping server shows a
// "waking up" state instead of an empty account.
export default function Page() {
  return <DashboardPage />;
}
