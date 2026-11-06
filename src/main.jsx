import React from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { RouterProvider, createRouter, createRootRoute, createRoute } from '@tanstack/react-router';
import App from './App.jsx';
import './style.css';
import './details.css';

const queryClient = new QueryClient();
const rootRoute = createRootRoute({ component: App });
const indexRoute = createRoute({ getParentRoute: () => rootRoute, path: '/', component: () => null });
const routeTree = rootRoute.addChildren([indexRoute]);
const router = createRouter({ routeTree });
createRoot(document.getElementById('root')).render(<React.StrictMode><QueryClientProvider client={queryClient}><RouterProvider router={router}/></QueryClientProvider></React.StrictMode>);
