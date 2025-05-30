# Group
The [`rblxopencloud.Group`][rblxopencloud.Group] object allows access to groups. Currently there is only read only access, but write access is coming soon.

## Fetching Group Information

### Basic Group Info

You can get group information, such as it's name, description, member count, owner, etc by using [`Group.fetch_info`][rblxopencloud.Group.fetch_info]. The method will update the [`rblxopencloud.Group`][rblxopencloud.Group]'s attributes with the fetched info, and return itself. This is an example to print out the group's name, and member count.

```py
group = rblxopencloud.Group(0000000, "api-key")

group.fetch_info()

print(f"{group.name} has {group.member_count} members!")
```

There are no permission restrictions for basic group information, any API key/OAuth2 bearer can get basic information for any group.

### Listing Group Members

You can list all members in a group using the [`Group.list_members`][rblxopencloud.Group.list_members] method. It will take effitively forever to complete iteration in very large groups. This example will print the user ID, and user's group role ID for every member in a group:

```py
for member in group.list_members():
    print(member.id, member.role_id)
```

You can list all members in a specific role like this:

```py
for member in group.list_members(role_id=0000000):
    print(member.id)
```

Just like with basic group info, there are no restrictions on who can list group members, anyone can list group members of any group.

### Listing Group Roles

You can list all roles in a group using the [`Group.list_roles`][rblxopencloud.Group.list_roles] method. It will iterate through every role, including the Guest role, and provide the role's id, name, rank, permission, etc. Here is an example to list every role in the Group:

```py
for role in group.list_roles():
    print(role.id, role.rank, role.name, role.member_count)
```

Just like with the previous two methods, there is no restrictions on listing roles, however, limitations do apply for what information is returned. A role's description is only returned if the authorized user is the group owner, and permission information is only returned for the guest role, and the authorizing user's role (if they're not a guest), unless the authorizing user is the group owner - then permissions for all roles is returned.

### Fetch Group Shout

You can fetch the group's current shout using the [`Group.fetch_shout`][rblxopencloud.Group.fetch_shout]. Here is an example to get the group shout:

```py
shout = group.fetch_shout()

print(shout.user.id, shout.content)
```

Note that the authorizing user requires the 'View group shout' permission on their current role, or the Guest role if you're not in the group.

## Uploading Assets

You can upload images, audio, and models to a Group using the [`Group.upload_asset`][rblxopencloud.Group.upload_asset] method. It requires an API key owned by the Group with read and write Asset API permissions. The following example will upload the image at the path `path-to/image.png` and wait until it is complete:

```py
with open("path-to/image.png", "rb") as file:
    operation = group.upload_asset(file, rblxopencloud.AssetType.Decal, "asset name", "asset description")

asset = operation.wait()
print(asset)
```

!!! danger
    Avoid uploading assets to Roblox that you don't have full control over, such as AI generated assets or content created by unknown people. Assets uploaded that break Roblox's Terms of Services can get your account moderated.

    For OAuth2 developers, it has been confirmed by Roblox staff [in this DevForum post](https://devforum.roblox.com/t/2401354/36), that your app will not be punished if a malicious user uses it to upload Terms of Service violating content, and instead the authorizing user's account will be punished.

You can update model assets using [`Group.update_asset`][rblxopencloud.Group.update_asset].