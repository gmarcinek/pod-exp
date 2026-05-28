import { DebateViewRoute } from "../routes/debate-view-route";
import { DebatesRoute } from "../routes/debates-route";
import { HomeRoute } from "../routes/home-route";
import { NewDebateRoute } from "../routes/new-debate-route";
import type { BootstrapPayload } from "./bootstrap-data";

type AppRouterProps = {
  bootstrap: BootstrapPayload;
};

export function AppRouter({ bootstrap }: AppRouterProps) {
  switch (bootstrap.route) {
    case "debates":
      return <DebatesRoute data={bootstrap.initialData} />;
    case "new-debate":
      return <NewDebateRoute data={bootstrap.initialData} />;
    case "debate-view":
      return <DebateViewRoute data={bootstrap.initialData} />;
    case "home":
    default:
      return <HomeRoute data={bootstrap.initialData} />;
  }
}