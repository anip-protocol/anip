package dev.anip.graphql;

import graphql.language.ArrayValue;
import graphql.language.BooleanValue;
import graphql.language.FloatValue;
import graphql.language.IntValue;
import graphql.language.NullValue;
import graphql.language.ObjectValue;
import graphql.language.StringValue;
import graphql.language.Value;
import graphql.schema.Coercing;
import graphql.schema.CoercingParseLiteralException;
import graphql.schema.GraphQLScalarType;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * Custom scalar types for the ANIP GraphQL schema.
 */
public class ExtendedScalars {

    private ExtendedScalars() {}

    /**
     * JSON scalar: accepts/returns arbitrary JSON values.
     */
    public static final GraphQLScalarType JSON = GraphQLScalarType.newScalar()
            .name("JSON")
            .description("Arbitrary JSON value")
            .coercing(new Coercing<Object, Object>() {
                @Override
                public Object serialize(Object dataFetcherResult) {
                    return dataFetcherResult;
                }

                @Override
                public Object parseValue(Object input) {
                    return input;
                }

                @Override
                public Object parseLiteral(Object input) {
                    return parseLiteralValue(input);
                }
            })
            .build();

    @SuppressWarnings("unchecked")
    private static Object parseLiteralValue(Object input) {
        if (input instanceof StringValue sv) {
            return sv.getValue();
        }
        if (input instanceof IntValue iv) {
            return iv.getValue().intValue();
        }
        if (input instanceof FloatValue fv) {
            return fv.getValue().doubleValue();
        }
        if (input instanceof BooleanValue bv) {
            return bv.isValue();
        }
        if (input instanceof NullValue) {
            return null;
        }
        if (input instanceof ArrayValue av) {
            return av.getValues().stream()
                    .map(ExtendedScalars::parseLiteralValue)
                    .collect(Collectors.toList());
        }
        if (input instanceof ObjectValue ov) {
            Map<String, Object> map = new LinkedHashMap<>();
            ov.getObjectFields().forEach(f -> map.put(f.getName(), parseLiteralValue(f.getValue())));
            return map;
        }
        return null;
    }
}
