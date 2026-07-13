import { AgentsRoute } from "../routes/agents-route";
import { DebateViewRoute } from "../routes/debate-view-route";
import { DebatesRoute } from "../routes/debates-route";
import { EditorialsRoute } from "../routes/editorials-route";
import { EditorialRoute } from "../routes/editorial-route";
import { FederationRoute } from "../routes/federation-route";
import { FederationViewRoute } from "../routes/federation-view-route";
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
    case "editorials":
      return <EditorialsRoute data={bootstrap.initialData} />;
    case "new-debate":
      return <NewDebateRoute data={bootstrap.initialData} />;
    case "editorial":
      return <EditorialRoute data={bootstrap.initialData} />;
    case "debate-view":
      return <DebateViewRoute data={bootstrap.initialData} />;
    case "federation":
      return <FederationRoute data={bootstrap.initialData} />;
    case "federation-view":
      return <FederationViewRoute data={bootstrap.initialData} />;
    case "agents":
      return <AgentsRoute data={bootstrap.initialData} />;
    case "home":
    default:
      return <HomeRoute data={bootstrap.initialData} />;
  }
}
