from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericRelation
from django.core.exceptions import ValidationError, ObjectDoesNotExist

from django.contrib.postgres.fields import HStoreField

from dominate.tags import *

from hs_core.models import ResourceFile, AbstractMetaDataElement, Coverage


class AbstractFileMetaData(models.Model):
    """ base class for HydroShare file type metadata """

    # one temporal coverage and one spatial coverage
    coverages = GenericRelation(Coverage)
    # kye/value metadata
    extra_metadata = HStoreField(default={})

    class Meta:
        abstract = True

    def delete_all_elements(self):
        self.coverages.all().delete()

    def get_html(self):
        # subclass must override
        # returns a string representing html code for display of metadata in view mode
        # self.extra_metadata = {'key-1': 'value-1', 'key-2': 'value-2'}
        if self.extra_metadata:
            root_div = div(cls="col-sm-12 content-block")
            with root_div:
                legend('Extended Metadata')
                with table(cls="table table-striped funding-agencies-table"):
                    with tbody():
                        with tr(cls="header-row"):
                            th("Key")
                            th("Value")
                        for k, v in self.extra_metadata.iteritems():
                            with tr(data_key=k):
                                td(k)
                                td(v)

            return root_div.render()
        else:
            return ""

    def get_html_forms(self):
        # self.extra_metadata = {'key-1': 'value-1', 'key-2': 'value-2'}
        if self.extra_metadata:
            root_div = div(cls="col-sm-12 content-block", id="filetype-extra-metadata")
            with root_div:
                legend('Extended Metadata')
                with a(cls="btn btn-success", type="button", data_toggle="modal",
                       data_target="#add-keyvalue-filetype-modal"):
                    with span(cls="glyphicon glyphicon-plus"):
                        span("Add Key/Value", cls="button-label")
                with table(cls="table table-striped funding-agencies-table"):
                    with tbody():
                        with tr(cls="header-row"):
                            th("Key")
                            th("Value")
                            th("Actions")
                        for k, v in self.extra_metadata.iteritems():
                            with tr(data_key=k):
                                td(k)
                                td(v)
                                with td():
                                    a(data_toggle="modal", data_placement="auto", title="Edit",
                                      cls="glyphicon glyphicon-pencil icon-button icon-blue",
                                      data_target="#edit-keyvalue-filetype-{}".format(k))
                                    a(data_toggle="modal", data_placement="auto", title="Remove",
                                      cls="glyphicon glyphicon-trash icon-button btn-remove",
                                      data_target="#delete-keyvalue-filetype-{}".format(k))
                self._get_add_key_value_modal_form()
            return root_div
        else:
            return self._get_add_key_value_modal_form()

    def has_all_required_elements(self):
        return True

    @classmethod
    def get_supported_element_names(cls):
        return ['Coverage']

    @property
    def has_metadata(self):
        if not self.coverages.all() and not self.extra_metadata:
            return False
        return True

    @property
    def spatial_coverage(self):
        return self.coverages.exclude(type='period').first()

    @property
    def temporal_coverage(self):
        return self.coverages.filter(type='period').first()

    def create_element(self, element_model_name, **kwargs):
        # had to import here to avoid circular import
        from hs_file_types.utils import update_resource_coverage_element
        model_type = self._get_metadata_element_model_type(element_model_name)
        kwargs['content_object'] = self
        element = model_type.model_class().create(**kwargs)
        if element_model_name.lower() == "coverage":
            resource = element.metadata.logical_file.resource
            update_resource_coverage_element(resource)
        return element

    def update_element(self, element_model_name, element_id, **kwargs):
        # had to import here to avoid circular import
        from hs_file_types.utils import update_resource_coverage_element
        model_type = self._get_metadata_element_model_type(element_model_name)
        kwargs['content_object'] = self
        model_type.model_class().update(element_id, **kwargs)
        if element_model_name.lower() == "coverage":
            element = model_type.model_class().objects.get(id=element_id)
            resource = element.metadata.logical_file.resource
            update_resource_coverage_element(resource)

    def delete_element(self, element_model_name, element_id):
        model_type = self._get_metadata_element_model_type(element_model_name)
        model_type.model_class().remove(element_id)

    def _get_metadata_element_model_type(self, element_model_name):
        element_model_name = element_model_name.lower()
        if not self._is_valid_element(element_model_name):
            raise ValidationError("Metadata element type:%s is not one of the "
                                  "supported metadata elements."
                                  % element_model_name)

        unsupported_element_error = "Metadata element type:%s is not supported." \
                                    % element_model_name
        try:
            model_type = ContentType.objects.get(app_label='hs_geo_raster_resource',
                                                 model=element_model_name)
        except ObjectDoesNotExist:
            try:
                model_type = ContentType.objects.get(app_label='hs_core',
                                                     model=element_model_name)
            except ObjectDoesNotExist:
                raise ValidationError(unsupported_element_error)

        if not issubclass(model_type.model_class(), AbstractMetaDataElement):
            raise ValidationError(unsupported_element_error)

        return model_type

    def _is_valid_element(self, element_name):
        allowed_elements = [el.lower() for el in self.get_supported_element_names()]
        return element_name.lower() in allowed_elements

    @classmethod
    def validate_element_data(cls, request, element_name):
        raise NotImplementedError

    def _get_add_key_value_modal_form(self):
        form_action = "/hsapi/_internal/{0}/{1}/update-file-keyvalue-metadata/"
        form_action = form_action.format(self.logical_file.__class__.__name__, self.logical_file.id)
        modal_div = div(cls="modal fade", id="add-keyvalue-filetype-modal", tabindex="-1",
                        role="dialog", aria_labelledby="add-key-value-metadata",
                        aria_hidden="true")
        with modal_div:
            with div(cls="modal-dialog", role="document"):
                with div(cls="modal-content"):
                    with form(action=form_action, id="add-keyvalue-filetype-metadata",
                              method="post", enctype="multipart/form-data"):
                        div("{% csrf_token %}")
                        with div(cls="modal-header"):
                            button("x", type="button", cls="close", data_dismiss="modal",
                                   aria_hidden="true")
                            h4("Add/Update Key/Value Metadata", cls="modal-title",
                               id="add-key-value-metadata")
                        with div(cls="modal-body"):
                            with div(cls="form-group"):
                                with div(cls="control-group"):
                                    label("Name", cls="control-label requiredField",
                                          fr="file_extra_meta_name")
                                    with div(cls="controls"):
                                        input(cls="form-control input-sm textinput textInput",
                                              id="file_extra_meta_name", maxlength="100",
                                              name="name", type="text")
                                with div(cls="control-group"):
                                    label("Value", cls="control-label requiredField",
                                          fr="file_extra_meta_value")
                                    with div(cls="controls"):
                                        textarea(cls="form-control input-sm textarea",
                                                 cols="40", rows="10",
                                                 id="file_extra_meta_value",
                                                 name="value", type="text")
                        with div(cls="modal-footer"):
                            button("Cancel", type="button", cls="btn btn-default",
                                   data_dismiss="modal")
                            button("OK", type="button", cls="btn btn-primary",
                                   onclick="updateFileTypeExtraMetadata(); return true;")
        return modal_div


class AbstractLogicalFile(models.Model):
    """ base class for HydroShare file types """

    # mime type of the dominant file in the group - not sure if we need this
    mime_type = models.CharField(max_length=1000, default='')
    # files associated with this logical file group
    files = GenericRelation(ResourceFile, content_type_field='logical_file_content_type',
                            object_id_field='logical_file_object_id')
    # the dataset name will allow us to identify a logical file group on user interface
    dataset_name = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        abstract = True

    @classmethod
    def get_allowed_uploaded_file_types(cls):
        # any file can be part of this logical file group - subclass needs to override this
        return [".*"]

    @classmethod
    def get_allowed_storage_file_types(cls):
        # can store any file types in this logical file group - subclass needs to override this
        return [".*"]

    @classmethod
    def type_name(cls):
        return cls.__name__

    @property
    def has_metadata(self):
        return hasattr(self, 'metadata')

    @property
    def size(self):
        # get total size (in bytes) of all files in this file type
        return sum([f.size for f in self.files.all()])

    @property
    def resource(self):
        return self.files.all().first().resource

    def logical_delete(self, user):
        # deletes the logical file as well as all resource files associated with this logical file
        from hs_core.hydroshare.resource import delete_resource_file
        self.delete_metadata()
        # delete all resource files associated with this instance of logical file
        for f in self.files.all():
            delete_resource_file(f.resource.short_id, f.id, user,
                                 delete_logical_file=False)

        # delete logical file first then delete the associated metadata file object
        metadata = self.metadata
        super(AbstractLogicalFile, self).delete()
        metadata.delete()

    def delete_metadata(self):
        # delete all metadata associated with this file type
        if self.has_metadata:
            self.metadata.delete_all_elements()
