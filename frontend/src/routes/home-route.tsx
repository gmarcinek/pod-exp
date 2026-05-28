import type { HomeBootstrapData } from "../lib/types/bootstrap";
import { HomePage } from "../modules/home/home-page";

type HomeRouteProps = {
  data: HomeBootstrapData;
};

export function HomeRoute({ data }: HomeRouteProps) {
  return <HomePage agents={data.agents} models={data.models} />;
}