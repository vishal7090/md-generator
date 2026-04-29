package r;

import javax.validation.constraints.NotNull;

public class RulesBean {

    @NotNull
    public void save(@NotNull String id) {
        if (id == null) {
            throw new IllegalArgumentException("id required");
        }
    }
}
