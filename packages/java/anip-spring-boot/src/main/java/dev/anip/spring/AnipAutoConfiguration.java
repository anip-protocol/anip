package dev.anip.spring;

import dev.anip.service.ANIPService;

import org.springframework.boot.autoconfigure.condition.ConditionalOnBean;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * Auto-configuration that creates ANIP controller and lifecycle beans
 * when an {@link ANIPService} bean is present.
 */
@Configuration
@ConditionalOnBean(ANIPService.class)
public class AnipAutoConfiguration {

    @Bean
    public AnipController anipController(ANIPService service) {
        return new AnipController(service);
    }

    @Bean
    public AnipLifecycle anipLifecycle(ANIPService service) {
        return new AnipLifecycle(service);
    }
}
