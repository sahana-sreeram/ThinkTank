
import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarHeader,
} from '@/components/ui/sidebar';
import { FolderOpen, Users, Calendar, Home, FileText } from 'lucide-react';

const navigation = [
  { title: 'Dashboard',        url: '/',                icon: Home      },
  { title: 'Policy Briefing',  url: '/policy',          icon: FileText  },
  { title: 'Project Manager',  url: '/projects',        icon: FolderOpen},
  { title: 'Expert Manager',   url: '/experts',         icon: Users     },
  { title: 'Meetings',         url: '/meetings',        icon: Calendar  },
];

export function AppSidebar() {
  const location = useLocation();

  return (
    <Sidebar>
      <SidebarHeader className="border-b border-slate-800">
        <div className="px-4 py-5">
          <div className="text-[10px] font-mono tracking-[0.2em] text-slate-500 uppercase mb-1">
            Classification: Internal
          </div>
          <h1 className="text-sm font-bold tracking-widest text-slate-100 uppercase">
            ThinkTank
          </h1>
          <div className="text-[10px] font-mono text-slate-500 mt-0.5">
            Policy Intelligence System
          </div>
        </div>
      </SidebarHeader>

      <SidebarContent className="pt-2">
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu className="px-2 space-y-0.5">
              {navigation.map((item) => {
                const Icon = item.icon;
                const isActive =
                  item.url === '/'
                    ? location.pathname === '/'
                    : location.pathname.startsWith(item.url);
                return (
                  <SidebarMenuItem key={item.title}>
                    <SidebarMenuButton asChild isActive={isActive}>
                      <Link
                        to={item.url}
                        className={`flex items-center gap-3 px-3 py-2 rounded-md text-xs font-medium transition-colors ${
                          isActive
                            ? 'bg-slate-700 text-slate-100'
                            : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'
                        }`}
                      >
                        <Icon className="h-3.5 w-3.5 shrink-0" />
                        <span>{item.title}</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                );
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      {/* Footer classification bar */}
      <div className="absolute bottom-0 left-0 right-0 px-4 py-3 border-t border-slate-800">
        <div className="text-[9px] font-mono text-slate-600 text-center tracking-widest uppercase">
          THINKTANK // LOCAL-FIRST // v2.0
        </div>
      </div>
    </Sidebar>
  );
}
