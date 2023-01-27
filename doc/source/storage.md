# Storage

All the user-generated content (images and such) will need to be stored
somewhere. Since we adhere to the 12-factors principles, we can't be storing
those images on the local filesystem. We need to use a remote storage backend:

-   Servers and containers can be stateless (if you delete it you don't lose all
    your media)
-   If you copy one environment to another (for example dev to local) you can
    keep the same storage and avoid copying gigabytes of files

The gold standard of storage is Amazon S3. It's cheap, reliable, and has been
implemented by every major competitor. We use it through the `django-storages`
package.

Those values are highly infrastructure-dependent, if you're a developer there is
probably a SRE/system admin/DevOps person you need to talk to.

## Configuration

We have two modes of operation:

-   `do` &mdash; Using DigitalOcean's Spaces as a storage backend. While it's
    less powerful than the native S3, it's also much simpler. In simple projects
    it makes sense to use it over AWS's one.
-   `s3` &mdash; Is the real one. It has endless options and endless ways to get
    lost.

The mode is set by the `STORAGES_MODE` environment variable. If it's not set,
then we default to `s3`.

### Common settings

-   `STORAGE_BUCKET_NAME` &mdash; The name of the bucket to use.
-   `STORAGE_MAKE_FILES_PUBLIC` &mdash; If set to `true`, then all the files
    will be made public. This is the case when you're only hosting
    user-generated content that should be made public, like images in a CMS. If
    you enable this mode, you need to set another variable:
    -   `AWS_S3_CUSTOM_DOMAIN` &mdash; The domain name of the CDN that has been
        configured in front of the bucket. In DigitalOcean it's an option to
        enable in the bucket, in AWS you need to create a CloudFront
        distribution in front of the bucket.

### DigitalOcean Spaces

When running in `do` mode, the following settings are used:

-   `DO_REGION` &mdash; The region to use. It's a string, for example `ams3` by
    default.
-   `AWS_ACCESS_KEY_ID` &mdash; DigitalOcean-provided access key ID.
-   `AWS_SECRET_ACCESS_KEY` &mdash; DigitalOcean-provided secret access key.

### AWS

When running in `s3` mode, you need to set the following settings **only** if
you're not running from an AWS instance (Fargate container, EC2 VM, etc):

-   `AWS_ACCESS_KEY_ID` &mdash; IAM-provided access key ID.
-   `AWS_SECRET_ACCESS_KEY` &mdash; IAM-provided secret access key.

```{note}
If you're running from an AWS instance, you don't need to set those variables,
as they are automatically deduced by boto3. This is true for anything
boto3-related.
```
