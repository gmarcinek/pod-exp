import { HomePage } from "../modules/home/home-page";
import type { HomeBootstrapData } from "../lib/types/bootstrap";

type HomeRouteProps = {
  data: HomeBootstrapData;
};

export function HomeRoute({ data }: HomeRouteProps) {
  return <HomePage agents={data.agents} models={data.models} />;
}