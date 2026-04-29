package com.example;

import javax.portlet.GenericPortlet;
import javax.portlet.RenderRequest;
import javax.portlet.RenderResponse;
import javax.portlet.ProcessAction;
import javax.portlet.ActionRequest;
import javax.portlet.ActionResponse;

public class SamplePortlet extends GenericPortlet {

    @ProcessAction(name = "submit")
    public void processSubmit(ActionRequest request, ActionResponse response) {
        // action
    }

    @Override
    protected void doView(RenderRequest request, RenderResponse response) {
        // view
    }
}
