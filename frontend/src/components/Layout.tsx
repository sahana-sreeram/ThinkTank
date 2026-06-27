
import React from 'react';
import { SidebarProvider, SidebarInset, SidebarTrigger } from '@/components/ui/sidebar';
import { AppSidebar } from '@/components/AppSidebar';

interface LayoutProps {
  children: React.ReactNode;
}

const Layout: React.FC<LayoutProps> = ({ children }) => {
  return (
    <SidebarProvider>
      <div className="min-h-screen flex w-full bg-slate-50">
        <AppSidebar />
        <SidebarInset className="flex-1 min-h-screen">
          <header className="flex h-12 items-center gap-3 border-b border-slate-200 bg-white/80 backdrop-blur-sm px-4 sticky top-0 z-10">
            <SidebarTrigger className="text-slate-500 hover:text-slate-900" />
            <div className="h-4 w-px bg-slate-200" />
            <span className="text-[10px] font-mono text-slate-400 tracking-widest uppercase">
              Policy Intelligence Platform
            </span>
          </header>
          <main className="flex-1">
            {children}
          </main>
        </SidebarInset>
      </div>
    </SidebarProvider>
  );
};

export default Layout;
