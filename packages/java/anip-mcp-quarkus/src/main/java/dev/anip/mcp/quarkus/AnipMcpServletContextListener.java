package dev.anip.mcp.quarkus;

import dev.anip.service.ANIPService;

import io.modelcontextprotocol.server.transport.HttpServletStreamableServerTransportProvider;

import jakarta.inject.Inject;
import jakarta.servlet.ServletContext;
import jakarta.servlet.ServletContextEvent;
import jakarta.servlet.ServletContextListener;
import jakarta.servlet.ServletRegistration;
import jakarta.servlet.annotation.WebListener;

/**
 * Registers the MCP Streamable HTTP servlet in the Quarkus Undertow container.
 *
 * <p>Quarkus Undertow discovers {@link WebListener}-annotated classes
 * and invokes them during servlet context initialization, allowing
 * programmatic servlet registration.
 */
@WebListener
public class AnipMcpServletContextListener implements ServletContextListener {

    @Inject
    ANIPService service;

    @Override
    public void contextInitialized(ServletContextEvent sce) {
        try {
            HttpServletStreamableServerTransportProvider transport =
                    AnipMcpQuarkus.mount(service, "/mcp", true);

            ServletContext ctx = sce.getServletContext();
            ServletRegistration.Dynamic reg = ctx.addServlet("anip-mcp", transport);
            reg.addMapping("/mcp");
            reg.setAsyncSupported(true);
        } catch (Throwable t) {
            System.err.println("MCP HTTP transport not available: " + t.getMessage());
        }
    }
}
