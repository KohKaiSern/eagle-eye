import { mount } from "svelte";

import App from "./App.svelte";
import "./app.css";

const target = document.querySelector<HTMLElement>("#app");
if (!target) throw new Error("Could not find the application mount point.");

mount(App, { target });
