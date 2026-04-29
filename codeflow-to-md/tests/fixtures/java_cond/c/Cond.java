package c;

public class Cond {

    void caller() {
        if (userIsActive()) {
            target();
        }
        int x = ok() ? yes() : no();
    }

    boolean userIsActive() {
        return true;
    }

    void target() {}

    boolean ok() {
        return true;
    }

    void yes() {}

    void no() {}
}
